"""
네이버 뉴스 검색 결과에서 URL 추출 모듈 (수정본)

- 무한스크롤 방식 대응 (&start 파라미터 증분)
- 네이버‧원본 기사 URL 동시 수집
- 중복 URL 제거 후 JSON 저장 기능
"""

import os
from difflib import SequenceMatcher
import re
import json
import time
import random
import logging
from datetime import datetime
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------
# 로깅 설정
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding='utf-8'  # 인코딩 설정 추가
)
logger = logging.getLogger("naver_news_url_extractor")


class NaverNewsURLExtractor:
    """네이버 뉴스 URL 추출기"""

    def __init__(self, output_dir: str = "url_data"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        # 간단한 User-Agent 랜덤화 (차단 회피)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        ]

    # ------------------------------------------------------------------
    # 중복 및 유사도 확인 유틸
    # ------------------------------------------------------------------
    def is_similar_title(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """
        두 제목의 유사도 검사
        
        Args:
            title1: 첫 번째 제목
            title2: 두 번째 제목
            threshold: 유사도 임계값 (0.0-1.0)
            
        Returns:
            bool: 유사도가 임계값 이상인지 여부
        """
        if not title1 or not title2:
            return False
            
        # 짧은 제목들은 특별 처리 (예: 6글자 이하면 정확히 일치해야 함)
        if len(title1) <= 6 or len(title2) <= 6:
            return title1 == title2
            
        similarity = SequenceMatcher(None, title1, title2).ratio()
        return similarity >= threshold
        
    def filter_duplicate_news(self, news_items: List[Dict[str, any]], 
                             title_key: str = 'title', 
                             threshold: float = 0.8) -> List[Dict[str, any]]:
        """
        유사 제목 기반 중복 필터링
        
        Args:
            news_items: 뉴스 항목 목록
            title_key: 제목이 포함된 키 이름
            threshold: 유사도 임계값
            
        Returns:
            List[Dict[str, any]]: 중복이 제거된 뉴스 항목 목록
        """
        unique_news = []
        titles = []
        
        for news in news_items:
            title = news.get(title_key, '')
            if not title:  # 제목이 없으면 일단 포함
                unique_news.append(news)
                continue
                
            is_duplicate = False
            for existing_title in titles:
                if self.is_similar_title(title, existing_title, threshold):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_news.append(news)
                titles.append(title)
        
        return unique_news
    def _get_headers(self) -> Dict[str, str]:
        return {"User-Agent": random.choice(self.user_agents)}

    def get_page_content(self, url: str, retries: int = 3) -> str | None:
        """URL에서 HTML 가져오기 (+재시도)"""
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=self._get_headers(), timeout=8)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                logger.warning("요청 오류 %s (시도 %d/%d)", e, attempt + 1, retries)
                time.sleep(2 ** attempt) # 지수 백오프
        logger.error("재시도 실패: %s", url)
        return None

    # ------------------------------------------------------------------
    # HTML 파싱
    # ------------------------------------------------------------------
    NAVER_PATTERN = re.compile(r"https?://n\.news\.naver\.com/.+/article/")

    def extract_news_urls(self, html: str) -> List[Dict[str, str]]:
        """검색 결과 HTML에서 기사 URL 목록 추출"""
        soup = BeautifulSoup(html, "html.parser")
        results: List[Dict[str, str]] = []

        # 네이버 뉴스 URL (모바일·PC 공통 구조 타겟팅 - 좀 더 구체적인 선택자 사용 고려)
        # 예: div.news_wrap a.news_tit[href*='n.news.naver.com']
        # 현재는 넓은 범위의 a 태그에서 href 속성으로 필터링
        for a_tag in soup.select('a[href]'):
            href = a_tag.get("href", "")
            if self.NAVER_PATTERN.search(href):
                # 추가적인 검증 (예: 링크 텍스트가 있는지, 특정 클래스 내부에 있는지 등)
                # 일반적인 링크가 아닌 실제 기사 링크인지 확인하는 로직이 필요할 수 있음
                # 예를 들어, 'news.naver.com'을 포함하면서도 광고나 관련없는 링크가 있을 수 있음
                # 여기서는 일단 패턴 매칭만으로 추가
                 results.append({"type": "naver", "url": href})


        # 원본 기사 URL (news_tit 링크)
        # 네이버 뉴스 검색 결과 페이지의 HTML 구조에 따라 이 선택자는 변경될 수 있습니다.
        # 최신 구조에서는 `div.news_contents div.dsc_wrap a.dsc_thumb.type_image[href]` 또는
        # `div.news_area a.news_tit[href]` 등이 사용될 수 있습니다.
        # 좀 더 안정적인 선택자를 위해 실제 HTML 구조를 주기적으로 확인할 필요가 있습니다.
        for a in soup.select("div.news_area a.news_tit[href], div.news_wrap a.news_tit[href]"): # 일반적인 뉴스 제목 링크
            href = a["href"]
            # 네이버 URL 제외
            if not self.NAVER_PATTERN.search(href):
                results.append({"type": "original", "url": href})
        
        # 다른 구조에서의 원본 기사 URL (예: 썸네일 링크 등)
        # for a in soup.select("div.news_contents a.dsc_thumb[href]"): # 썸네일 이미지 링크에서 가져오는 경우
        #     href = a["href"]
        #     if not self.NAVER_PATTERN.search(href):
        #         results.append({"type": "original", "url": href})


        # 중복 제거 (URL 기준)
        unique_items_by_url: Dict[str, Dict[str, str]] = {}
        for item in results:
            if item["url"] not in unique_items_by_url:
                unique_items_by_url[item["url"]] = item
        
        return list(unique_items_by_url.values())

    # ------------------------------------------------------------------
    # 메인 수집 로직
    # ------------------------------------------------------------------
    def collect_from_search(
        self,
        search_url: str,
        max_pages: int = 0, # 0 또는 음수 -> 무제한
        delay_sec: float = 1.0,
        max_urls: int = 0, # URL 수집 제한: 0 또는 음수 -> 제한 없음, 양수 -> 지정된 개수까지만 수집
        url_type_filter: str = None, # None -> 모든 유형, 'naver' -> 네이버 뉴스 URL만, 'original' -> 원본 URL만
        search_date: str = None, # 검색 날짜 정보 (YYYYMMDD)
    ) -> List[Dict[str, str]]:
        """네이버 검색 결과에서 URL 수집

        Parameters
        ----------
        search_url : str
            네이버 뉴스 검색 URL (start 파라미터 없음)
        max_pages : int, optional
            최대 페이지 수. 0 또는 음수 → 페이지 제한 없음. 양수 → 해당 페이지까지만 스캔.
        delay_sec : float, optional
            요청 간 최소 지연 (랜덤 0~1초 추가)
        max_urls : int, optional
            수집할 최대 URL 개수. 
            - 0 또는 음수: 제한 없이 모든 URL 수집
            - 양수: 지정된 개수까지만 수집 후 종료
        url_type_filter : str, optional
            URL 유형 필터 ('naver', 'original', None=모두)
        search_date : str, optional
            검색 날짜 정보 (YYYYMMDD). 현재 수집하는 날짜를 식별할 때 사용"""

        all_items_map: Dict[str, Dict[str, str]] = {} # URL을 키로 사용하여 중복 방지 및 아이템 저장
        page = 1
        consecutive_empty_pages = 0
        max_consecutive_empty_pages = 3  # 연속으로 빈 페이지가 나오면 종료 (새로운 URL이 없는 페이지)

        # 빠른 종료를 위한 조건 추가
        early_termination = False
        
        while not early_termination:
            # 네이버 뉴스 검색 URL은 'start=' 파라미터로 페이지네이션을 함 (1, 11, 21, ...)
            current_page_url = f"{search_url}&start={(page - 1) * 10 + 1}"
            logger.info(f"페이지 스캔 중: {page} (URL: {current_page_url})")
            
            html_content = self.get_page_content(current_page_url)
            if not html_content:
                logger.warning(f"{page} 페이지 콘텐츠 로드 실패. 다음 페이지로 넘어갑니다.")
                consecutive_empty_pages +=1 # 실패도 빈 페이지로 간주
                if consecutive_empty_pages >= max_consecutive_empty_pages:
                    logger.info(f"연속 {max_consecutive_empty_pages} 페이지 로드 실패 또는 새 URL 없음. 수집을 중단합니다.")
                    break
                page += 1
                if max_pages > 0 and page > max_pages: # max_pages 체크는 루프 하단에도 있음
                    break
                time.sleep(delay_sec + random.uniform(0, 0.5)) # 짧은 딜레이
                continue

            extracted_urls_on_page = self.extract_news_urls(html_content)
            
            # URL 유형 필터링 기능 구현
            if url_type_filter:
                extracted_urls_on_page = [item for item in extracted_urls_on_page if item.get('type') == url_type_filter]
                
            new_urls_found_on_this_page = 0
            for item in extracted_urls_on_page:
                if item["url"] not in all_items_map:
                    # 날짜 메타데이터 추가 (검색 날짜 정보)
                    if search_date:
                        item["search_date"] = search_date
                        
                    all_items_map[item["url"]] = item
                    new_urls_found_on_this_page += 1
                    
                    # URL 개수 제한 확인
                    if max_urls > 0 and len(all_items_map) >= max_urls:
                        logger.info(f"지정된 URL 수집 제한({max_urls}개)에 도달하여 수집을 조기 종료합니다.")
                        early_termination = True
                        break
            
            if early_termination:
                break
                
            if new_urls_found_on_this_page > 0:
                logger.info(f"{page} 페이지: 신규 URL {new_urls_found_on_this_page}건 발견 (누적 {len(all_items_map)}건)")
                consecutive_empty_pages = 0  # 새 URL 발견 시 카운터 리셋
            else:
                logger.info(f"{page} 페이지: 신규 URL 없음 (누적 {len(all_items_map)}건)")
                consecutive_empty_pages += 1

            # 루프 종료 조건
            if consecutive_empty_pages >= max_consecutive_empty_pages:
                logger.info(f"연속으로 {max_consecutive_empty_pages} 페이지 동안 새 URL이 발견되지 않아 수집을 종료합니다.")
                break
            
            if max_pages > 0 and page >= max_pages:
                logger.info(f"최대 페이지 수({max_pages})에 도달하여 수집을 종료합니다.")
                break

            page += 1
            time.sleep(delay_sec + random.uniform(0, 1)) # 다음 페이지 요청 전 딜레이

        # URL 개수 제한 적용 (안전장치)
        final_url_list = list(all_items_map.values())
        if max_urls > 0 and len(final_url_list) > max_urls:
            final_url_list = final_url_list[:max_urls]
            logger.info(f"URL 수집 제한({max_urls}개)을 적용하여 결과를 자릅니다.")
            
        logger.info(f"총 {len(final_url_list)}개의 고유 URL 수집 완료.")
        return final_url_list

    # ------------------------------------------------------------------
    # 저장 유틸
    # ------------------------------------------------------------------
    def save_urls_to_file(
        self,
        urls: List[Dict[str, str]],
        query: str | None = None,
        period: str | None = None,
        filename_prefix: str = "news_urls",
    ) -> str | None:
        """URL 목록을 JSON 저장"""
        if not urls:
            logger.warning("저장할 URL이 없습니다.")
            return None

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # 파일명에 query와 period를 포함시켜 구분 용이하게 (옵션)
        # safe_query = re.sub(r'[\\/*?:"<>|]', "", query)[:20] if query else "query"
        # safe_period = re.sub(r'[\\/*?:"<>|]', "", period) if period else "period"
        # filename = f"{filename_prefix}_{safe_query}_{safe_period}_{timestamp}.json"
        filename = f"{filename_prefix}_{timestamp}.json" # 기존 방식 유지
        
        filepath = os.path.join(self.output_dir, filename)

        data_to_save = {
            "query": query,
            "period": period, # 검색 옵션에 사용된 기간 문자열 (예: "1m", "20230101~20230131")
            "collection_timestamp": timestamp,
            "total_urls_collected": len(urls),
            "urls": urls,
        }
        try:
            with open(filepath, "w", encoding="utf-8") as fp:
                json.dump(data_to_save, fp, ensure_ascii=False, indent=4)
            logger.info(f"URL {len(urls)}건 저장 완료: {filepath}")
            return filepath
        except IOError as e:
            logger.error(f"파일 저장 중 오류 발생 ({filepath}): {e}")
            return None


# ----------------------------------------------------------------------
# CLI 테스트 (독립 실행용)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # 테스트용 검색 URL (예: "AI" 검색, 최근 1주)
    # 실제 테스트 시에는 NaverNewsSearchOption 클래스를 사용하여 URL을 동적으로 생성하는 것이 좋음
    from search_options import NaverNewsSearchOption # 테스트를 위해 임포트
    
    option = NaverNewsSearchOption("AI")
    option.set_period(NaverNewsSearchOption.PERIOD_1WEEK) # 예: 1주일
    test_search_url = option.build_url()
    
    logger.info(f"테스트 검색 URL: {test_search_url}")

    extractor = NaverNewsURLExtractor(output_dir="test_url_output") # 테스트용 출력 디렉토리
    collected_urls = extractor.collect_from_search(test_search_url, max_pages=2, delay_sec=1.5)
    
    if collected_urls:
        saved_file_path = extractor.save_urls_to_file(collected_urls, query="AI", period="1주일")
        if saved_file_path:
            logger.info(f"테스트 URL 저장 파일: {saved_file_path}")
            print("\n수집된 URL 샘플 (최대 5건):")
            for i, item in enumerate(collected_urls[:5], 1):
                print(f"{i}. Type: {item.get('type', 'N/A')}, URL: {item.get('url', 'N/A')}")
    else:
        logger.info("테스트 실행 결과: 수집된 URL 없음.")