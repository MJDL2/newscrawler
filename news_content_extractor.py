"""
네이버 뉴스 본문 추출 모듈

네이버 뉴스 URL에서 제목, 언론사, 게시일, 본문 등의 정보를 추출하는 기능을 제공합니다.
수집된 뉴스 본문은 검색어_대상검색기간_검색일시_(시작위치/전체) 형식으로 저장되며,
한 파일당 최대 20개의 기사가 저장됩니다.
"""

import requests
from bs4 import BeautifulSoup
import logging
import json
import os
import time
import random
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional # Optional 추가

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("tqdm 패키지가 설치되어 있지 않습니다. 프로그레스 바 기능이 비활성화됩니다.")
    print("pip install tqdm 명령으로 설치할 수 있습니다.")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'  # 인코딩 설정 추가
)
logger = logging.getLogger('naver_news_content_extractor')

class NaverNewsContentExtractor:
    """네이버 뉴스 본문 추출 클래스"""
    
    # 파일당 최대 저장 기사 수
    MAX_NEWS_PER_FILE = 20 # 클래스 변수로 유지
    
    def __init__(self, output_dir: str ='news_content', query: Optional[str] = None, period: Optional[str] = None):
        """
        네이버 뉴스 본문 추출기 초기화
        
        Args:
            output_dir (str): 추출한 뉴스 내용을 저장할 디렉토리
            query (str, optional): 검색어. 파일명 생성 등에 사용.
            period (str, optional): 검색 기간 설명. 파일명 생성 등에 사용.
        """
        self.output_dir = output_dir
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
        self.headers = {'User-Agent': self.user_agent}
        
        self.query = query if query else "unknown_query"
        self.period = period if period else "unknown_period"
        
        os.makedirs(self.output_dir, exist_ok=True)
    
    def load_urls_from_file(self, filepath: str) -> Tuple[List[str], Dict[str, any]]:
        """
        URL 목록 파일 로드 (JSON 또는 TXT)
        
        Args:
            filepath (str): URL 목록 파일 경로
            
        Returns:
            Tuple[List[str], Dict[str, any]]: 
                - 네이버 뉴스 URL 목록 (naver 타입만)
                - 원본 파일에서 추출한 메타데이터 (query, period, total_count 등)
        """
        urls: List[str] = []
        metadata: Dict[str, any] = {
            "query": self.query, # 기본값으로 초기화
            "period": self.period, # 기본값으로 초기화
            "original_total_urls": 0, # 파일에 명시된 전체 URL 수
            "naver_news_urls_count": 0 # 실제 추출된 네이버 뉴스 URL 수
        }
        
        if not os.path.exists(filepath):
            logger.error(f"URL 파일 없음: {filepath}")
            return urls, metadata

        _, ext = os.path.splitext(filepath)
        
        try:
            if ext.lower() == '.json':
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # JSON 파일 구조에 따라 메타데이터 및 URL 추출
                # url_extractor.py에서 저장하는 형식 기준으로 파싱
                metadata["query"] = data.get('query', self.query)
                metadata["period"] = data.get('period', self.period)
                url_items = data.get('urls', [])
                metadata["original_total_urls"] = data.get('total_urls_collected', len(url_items))
                
                # 네이버 뉴스 URL만 필터링
                urls = [item['url'] for item in url_items if isinstance(item, dict) and item.get('type') == 'naver' and 'url' in item]
            
            elif ext.lower() == '.txt':
                with open(filepath, 'r', encoding='utf-8') as f:
                    # TXT 파일은 한 줄에 URL 하나씩 있다고 가정, 네이버 뉴스 URL인지 검증 필요
                    raw_urls = [line.strip() for line in f if line.strip().startswith("http")]
                # 네이버 뉴스 URL 필터링 (간단한 체크)
                urls = [url for url in raw_urls if "news.naver.com" in url]
                metadata["original_total_urls"] = len(raw_urls)
                # TXT 파일의 경우 query, period는 extractor 초기값 사용
            
            else:
                logger.error(f"지원하지 않는 URL 파일 형식: {ext} ({filepath})")
                return [], metadata

            metadata["naver_news_urls_count"] = len(urls)
            logger.info(f"{filepath}에서 네이버 뉴스 URL {len(urls)}개 로드 완료.")

        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 오류: {filepath}")
        except Exception as e:
            logger.error(f"URL 파일 로드 중 오류 ({filepath}): {e}")
            
        return urls, metadata
    
    def get_page_content(self, url: str, retries: int = 3, timeout: int = 10, backoff_factor: float = 2.0) -> Optional[str]:
        """
        웹 페이지 내용 가져오기 (개선된 재시도 및 타임아웃 전략)
        
        Args:
            url: 요청할 URL
            retries: 최대 재시도 횟수
            timeout: 요청 타임아웃(초)
            backoff_factor: 재시도 간격을 결정하는 요소 (각 시도마다 backoff_factor^attempt 초 대기)
            
        Returns:
            페이지 내용 문자열 또는 실패 시 None
        """
        session = requests.Session()  # 세션 사용으로 연결 효율성 향상
        
        # User-Agent 랜덤화
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36'
        ]
        
        # 요청 헤더 구성
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Referer': 'https://search.naver.com/'
        }
        
        for attempt in range(retries):
            try:
                # 지수 백오프 적용 (첫 시도는 지연 없음)
                if attempt > 0:
                    sleep_time = backoff_factor ** attempt
                    logger.debug(f"재시도 {attempt}/{retries} - {sleep_time:.2f}초 대기 중...")
                    time.sleep(sleep_time)
                
                # 요청 실행
                response = session.get(
                    url, 
                    headers=headers, 
                    timeout=timeout,
                    allow_redirects=True  # 리다이렉트 허용
                )
                
                # 성공 여부 확인
                response.raise_for_status()
                
                # 인코딩 자동 감지
                if not response.encoding or response.encoding == 'ISO-8859-1':
                    response.encoding = response.apparent_encoding
                
                return response.text
                
            except requests.Timeout:
                logger.warning(f"요청 시간 초과 ({url}), 시도 {attempt+1}/{retries}")
            except requests.HTTPError as e:
                # HTTP 에러 상세 로깅
                status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'
                logger.warning(f"HTTP 오류 ({url}): {status_code}, 시도 {attempt+1}/{retries}")
                
                # 특정 상태 코드에 따른 다른 처리 가능
                if status_code == 404:  # 찾을 수 없음
                    logger.error(f"페이지를 찾을 수 없음 (404): {url}")
                    return None  # 404 오류는 재시도해도 해결되지 않으므로 바로 중단
                elif status_code == 429:  # Too Many Requests
                    # 429 오류는 더 긴 대기 시간 추가
                    extra_wait = 10 + random.uniform(1, 5)
                    logger.warning(f"너무 많은 요청 (429), 추가 {extra_wait:.1f}초 대기...")
                    time.sleep(extra_wait)
            except requests.RequestException as e:
                logger.warning(f"페이지 요청 오류 ({url}): {e}, 시도 {attempt+1}/{retries}")
            
        logger.error(f"최대 재시도 ({retries}회) 실패: {url}")
        return None
    
    def extract_news_content(self, url: str) -> Dict[str, str]:
        """
        단일 뉴스 URL에서 콘텐츠(제목, 언론사, 날짜, 본문, 기자) 추출
        언론사 별 본문 위치 선택자를 동적으로 처리
        """
        logger.debug(f"콘텐츠 추출 시도: {url}")
        news_data: Dict[str, str] = {
            'url': url, 'title': '', 'press': '', 'date': '', 'content': '', 'reporter': ''
        }
        
        html_content = self.get_page_content(url)
        if not html_content:
            return news_data # HTML 로드 실패 시 빈 데이터 반환

        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            # 제목 (여러 선택자 시도)
            title_selectors = [
                'h2.media_end_head_headline', 
                'div.media_end_head_title .media_end_head_headline', 
                '#ct > div.media_end_head.go_trans > div.media_end_head_title > h2',
                '.article_header h3',  # 추가: 다른 레이아웃 지원
                '.content h3.tit_view'  # 추가: 다른 언론사 레이아웃
            ]
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    news_data['title'] = title_elem.get_text(separator=' ', strip=True)
                    break
            
            # 언론사
            press_selectors = [
                'a.media_end_head_top_logo img', 
                'div.press_logo img',
                '.article_header .logo img',  # 추가: 다른 레이아웃
                '.press_logo_wrap img'  # 추가: 다른 레이아웃
            ]
            for selector in press_selectors:
                press_elem = soup.select_one(selector)
                if press_elem and press_elem.get('alt'):
                    news_data['press'] = press_elem['alt'].strip()
                    break
            
            # 날짜 및 시간 (여러 선택자 및 속성 시도)
            date_selectors_attrs = [
                ('span.media_end_head_info_datestamp_time', 'data-date-time'), # 최근 기사
                ('div.media_end_head_info_datestamp_time', 'data-date-time'), # 위와 동일할 수 있음
                ('div.media_end_head_info_datestamp span.media_end_head_info_datestamp_time', 'data-date-time'), # 구형?
                ('span.media_end_head_info_datestamp_time', 'data-modify-date-time'), # 수정 시간 우선
                ('div.article_info em', None), # 예전 기사 형식에서 텍스트로 된 날짜
                ('.article_header .date', None),  # 추가: 다른 레이아웃
                ('.article_info span.time', None)  # 추가: 다른 레이아웃
            ]
            for selector, attr_name in date_selectors_attrs:
                date_elem = soup.select_one(selector)
                if date_elem:
                    if attr_name and date_elem.has_attr(attr_name):
                        news_data['date'] = date_elem[attr_name].strip()
                        break
                    elif not attr_name: # 텍스트 내용 가져오기
                         full_date_text = date_elem.get_text(strip=True)
                         # "YYYY.MM.DD. 오후/오전 H:MM" 또는 "YYYY.MM.DD." 같은 형식에서 날짜 부분만 추출 시도
                         match = re.search(r"(\d{4}\.\d{2}\.\d{2}\.)", full_date_text)
                         if match:
                             news_data['date'] = match.group(1).replace('.', '-') + " " + full_date_text # 잠정적 포맷
                             break # YYYY-MM-DD 형식으로 변환하거나, 전체 텍스트 저장

            # 본문 (가장 중요한 부분, 여러 선택자 시도)
            # 네이버 뉴스 본문은 주로 'newsct_article', 'articleBodyContents' ID를 가짐
            content_selectors = [
                'div#newsct_article', 
                'div#articleBodyContents', 
                'div.article_body_contents',
                'div#articeBody',  # 추가: 다른 언론사 형식
                'div.news_content',  # 추가: 다른 언론사 형식
                'div.article_view_contents',  # 추가: 다른 언론사 형식
                '#articleBody'  # 추가: 다른 언론사 형식
            ]
            
            # 언론사 도메인 추출하여 언론사별 맞춤 선택자 추가
            domain_match = re.search(r'://([^/]+)', url)
            if domain_match:
                domain = domain_match.group(1)
                # 언론사별 맞춤 선택자 (필요시 확장)
                if 'sedaily.com' in domain:
                    content_selectors.insert(0, 'div.article_view')
                elif 'mk.co.kr' in domain:
                    content_selectors.insert(0, '#artText')
                elif 'hankyung.com' in domain:
                    content_selectors.insert(0, 'div.article-body')
                elif 'chosun.com' in domain:
                    content_selectors.insert(0, 'div.article-body')
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 불필요한 요소 (광고, '관련기사 더보기' 등) 제거
                    for el_to_remove in content_elem.select('.ad_wrap, .link_news_relation, .media_end_linked_more, .journalistcard_wrap, div[id*="AD"], script, style, .promotion_area'):
                        el_to_remove.decompose()
                    
                    # 텍스트 추출 방식 개선 (줄바꿈 유지 등)
                    # news_data['content'] = content_elem.get_text(separator='\n', strip=True)
                    
                    # 또는 각 p 태그나 div 태그를 순회하며 텍스트를 합치는 방식
                    paragraphs = []
                    for p in content_elem.find_all(['p', 'div'], recursive=False): # 직계 자식만 우선
                        text = p.get_text(strip=True)
                        if text: # 의미있는 텍스트가 있을 경우에만 추가
                            paragraphs.append(text)
                    if not paragraphs and content_elem: # 직계 자식에서 못찾으면 전체 텍스트
                        paragraphs.append(content_elem.get_text(strip=True))

                    news_data['content'] = "\n".join(paragraphs)

                    # 매우 짧은 본문은 다시 한번 확인
                    if len(news_data['content']) < 50 and content_elem.find_all('p'): # p태그가 있는데 짧으면 이상
                         news_data['content'] = content_elem.get_text(separator='\n', strip=True) # 전체 다시 시도
                    break

            # 기자 정보
            reporter_selectors = [
                '.media_end_head_journalist_name', # 최근 형식
                '.byline', # 추가: 다른 언론사 형식
                '.journalist', # 추가: 다른 언론사 형식
                '.article_footer .name', # 추가: 다른 언론사 형식
                '.reporter' # 추가: 다른 언론사 형식
            ]
            
            for selector in reporter_selectors:
                reporter_elem = soup.select_one(selector)
                if reporter_elem:
                    news_data['reporter'] = reporter_elem.get_text(strip=True)
                    break
            
            # 기자 정보가 없는 경우, 본문 마지막 부분에서 기자 정보 추출 시도
            if not news_data.get('reporter') and news_data.get('content'):
                reporter_pattern = r'([가-힣]{2,5}\s*(기자|특파원))'
                reporter_match = re.search(reporter_pattern, news_data['content'])
                if reporter_match:
                    news_data['reporter'] = reporter_match.group(1).strip()
            
            if news_data.get('title'): # 제목이라도 추출됐으면 성공으로 간주
                 logger.debug(f"콘텐츠 추출 성공: {news_data['title'][:30]}...")
            else:
                 logger.warning(f"콘텐츠 부분 추출 또는 실패: {url}")

        except Exception as e:
            logger.error(f"콘텐츠 파싱 중 예외 발생 ({url}): {e}", exc_info=True) # 상세 에러 로깅
        
        return news_data
    
    def save_news_content_batch(self, news_items_batch: List[Dict[str,str]], 
                                batch_start_index: int, 
                                overall_total_items: int,
                                file_timestamp: str) -> Optional[str]:
        """
        추출된 뉴스 내용 배치를 파일에 저장
        """
        if not news_items_batch:
            logger.warning("저장할 뉴스 데이터 배치 없음.")
            return None
        
        # 파일명 생성 (검색어, 기간, 타임스탬프, 페이지네이션 정보 포함)
        safe_query = re.sub(r'[\\/*?:"<>|]', "_", self.query)[:30]
        safe_period = re.sub(r'[\\/*?:"<>|]', "_", self.period).replace("~", "-")[:30]
        
        # 배치 범위 (1-based index)
        batch_end_index = batch_start_index + len(news_items_batch) -1
        pagination_info = f"{batch_start_index + 1}-{batch_end_index + 1}_total{overall_total_items}"
        
        filename = f"{safe_query}_{safe_period}_{file_timestamp}_{pagination_info}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        data_to_save = {
            "metadata": {
                "query": self.query,
                "period": self.period,
                "extraction_timestamp": file_timestamp, # 배치 파일 생성 시점의 타임스탬프
                "total_items_in_source": overall_total_items, # 원본 URL 목록의 전체 아이템 수
                "batch_range": f"{batch_start_index + 1}-{batch_end_index + 1}", # 이 배치의 범위 (1-based)
                "items_in_this_batch": len(news_items_batch)
            },
            "news_articles": news_items_batch
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            logger.info(f"뉴스 배치 저장 완료 ({len(news_items_batch)}건): {filepath}")
            return filepath
        except IOError as e:
            logger.error(f"뉴스 배치 파일 저장 오류 ({filepath}): {e}")
            return None

    def process_urls(self, urls_to_process: List[str], 
                     source_metadata: Dict[str, any], 
                     limit: Optional[int] = None, 
                     delay_sec: float = 1.0,
                     extraction_mode: str = 'sequential') -> Tuple[List[Dict[str, str]], List[str]]:
        """
        주어진 URL 목록을 처리하여 뉴스 콘텐츠를 추출하고 저장.
        
        Args:
            urls_to_process (List[str]): 처리할 네이버 뉴스 URL 목록.
            source_metadata (Dict[str, any]): URL 파일 로드 시 얻은 메타데이터.
            limit (Optional[int]): 처리할 최대 URL 수
                - None 또는 0 이하: 모든 URL 처리
                - 양수: 지정된 개수만큼만 처리
            delay_sec (float): 각 URL 요청 사이의 기본 지연 시간.
            extraction_mode (str): 추출 방식 
                - sequential: 순차적으로 처리
                - balanced: 전체 URL 중 균등하게 분포하여 선택
                - per_date: 날짜별로 균등하게 분포하여 선택
            
        Returns:
            Tuple[List[Dict[str, str]], List[str]]:
                - 추출된 모든 뉴스 데이터의 목록 (메모리에 누적).
                - 저장된 배치 파일 경로들의 목록.
        """
        if not urls_to_process:
            logger.warning("처리할 URL 목록이 비어있습니다.")
            return [], []
        
        # 균등 추출 모드 적용
        if extraction_mode != 'sequential' and limit and limit > 0:
            try:
                # balanced_extractor 모듈 동적 로드
                from balanced_extractor import extract_balanced_urls
                
                # URL 문자열 목록을 딕셔너리 목록으로 변환 (balanced_extractor에서 처리하기 위해)
                url_objects = []
                for url in urls_to_process:
                    # URL 정보를 딕셔너리로 구성
                    url_obj = {
                        "url": url,
                        "search_date": getattr(url, "search_date", None)  # URL 객체에 search_date가 있을 경우
                    }
                    url_objects.append(url_obj)
                    
                # 균등 추출 실행
                selected_url_objects = extract_balanced_urls(url_objects, limit, extraction_mode)
                
                # 선택된 URL 객체에서 URL 문자열 추출
                urls_for_processing = [obj["url"] for obj in selected_url_objects]
                logger.info(f"{extraction_mode} 방식으로 {len(urls_for_processing)}/{len(urls_to_process)} URL 선택됨")
                
            except ImportError:
                logger.warning("balanced_extractor 모듈을 로드할 수 없어 sequential 모드로 적용됩니다.")
                # 모듈 로드 실패 시 기존 방식으로 진행
                if limit is not None and limit > 0:
                    urls_for_processing = urls_to_process[:limit]
                    logger.info(f"URL 수 제한 적용: {limit}개만 처리 (원본 {len(urls_to_process)}개).")
                else:
                    urls_for_processing = urls_to_process
        else:
            # 실제 처리할 URL 목록 결정 (limit 적용)
            if limit is not None and limit > 0:
                urls_for_processing = urls_to_process[:limit]
                logger.info(f"본문 추출 제한 적용: {limit}개 URL만 처리 (원본 {len(urls_to_process)}개).")
            else:
                urls_for_processing = urls_to_process
        
        all_extracted_news_data: List[Dict[str, str]] = [] # 전체 추출 데이터 누적
        saved_batch_files: List[str] = [] # 저장된 파일 경로 목록
        
        current_batch_data: List[Dict[str,str]] = [] # 현재 배치에 담을 데이터
        
        # 파일명에 사용할 일관된 타임스탬프
        batch_file_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        total_urls_to_process = len(urls_for_processing)
        overall_items_in_source = source_metadata.get("naver_news_urls_count", total_urls_to_process)

        # 메모리 최적화: 배치 처리를 위한 변수
        memory_optimization = total_urls_to_process > 100  # 100개 이상의 URL을 처리할 때 메모리 최적화 활성화
        
        # tqdm 프로그레스 바 사용 (설치된 경우)
        if TQDM_AVAILABLE:
            url_iterator = tqdm(
                enumerate(urls_for_processing), 
                total=total_urls_to_process, 
                desc="뉴스 본문 추출", 
                unit="건"
            )
        else:
            url_iterator = enumerate(urls_for_processing)
        
        for idx, url in url_iterator:
            logger.info(f"URL 처리 중 ({idx + 1}/{total_urls_to_process}): {url}")
            
            # 지연 시간 (첫 요청 제외)
            if idx > 0:
                time.sleep(delay_sec + random.uniform(0, 0.5)) # 약간의 랜덤성 추가
            
            extracted_data = self.extract_news_content(url)
            
            # tqdm이 사용 중인 경우 프로그레스 바 대신 로깅하지 않음
            if not TQDM_AVAILABLE:
                logger.info(f"URL 처리 중 ({idx + 1}/{total_urls_to_process}): {url}")
            
            if extracted_data.get('title') or extracted_data.get('content'): # 제목이나 본문이 있어야 유효 데이터로 간주
                if not memory_optimization:
                    all_extracted_news_data.append(extracted_data)
                current_batch_data.append(extracted_data)
                
                # 배치 저장 조건 확인 (MAX_NEWS_PER_FILE 도달 또는 마지막 URL 처리 시)
                if len(current_batch_data) >= self.MAX_NEWS_PER_FILE or (idx + 1) == total_urls_to_process:
                    batch_start_index = (idx + 1) - len(current_batch_data) # 0-based index for this batch start in urls_for_processing
                    
                    saved_file = self.save_news_content_batch(
                        current_batch_data,
                        batch_start_index,
                        total_urls_to_process, # 현재 처리 대상이 된 URL 수 (limit 적용된 수)
                        batch_file_timestamp
                    )
                    if saved_file:
                        saved_batch_files.append(saved_file)
                    
                    # 메모리 최적화: 배치 저장 후 메모리에 저장된 배치 데이터 최소화
                    if memory_optimization:
                        if not all_extracted_news_data:
                            # 최소한 첫 배치는 전체 결과 확인용으로 메모리에 유지
                            all_extracted_news_data = current_batch_data.copy()
                        else:
                            # 대용량 처리 시 모든 데이터 대신 마지막 배치만 유지 (이전 배치는 파일에 저장됨)
                            if len(all_extracted_news_data) > self.MAX_NEWS_PER_FILE * 2:
                                all_extracted_news_data = all_extracted_news_data[-self.MAX_NEWS_PER_FILE:]
                            # 현재 배치 추가
                            all_extracted_news_data.extend(current_batch_data)
                    
                    current_batch_data = [] # 현재 배치 초기화
            else:
                logger.warning(f"유효한 콘텐츠 추출 실패: {url}")
        
        total_extracted = len(all_extracted_news_data)
        if memory_optimization and total_extracted < sum(len(json.loads(open(f, 'r', encoding='utf-8').read()).get('news_articles', [])) for f in saved_batch_files if os.path.exists(f)):
            logger.info(f"메모리 최적화로 인해 반환되는 결과 수({total_extracted})가 실제 저장된 전체 데이터보다 적습니다.")
        
        logger.info(f"총 {total_extracted}개의 뉴스 콘텐츠 추출 완료.")
        if saved_batch_files:
            logger.info(f"{len(saved_batch_files)}개의 배치 파일로 저장 완료.")
            
        return all_extracted_news_data, saved_batch_files

    def process_url_file(self, url_filepath: str, 
                         limit: Optional[int] = None, 
                         delay_sec: float = 1.0,
                         extraction_mode: str = 'sequential') -> List[Dict[str, str]]:
        """
        지정된 URL 파일(JSON 또는 TXT)을 읽어 뉴스 콘텐츠를 추출하고 저장.
        
        Args:
            url_filepath (str): URL 목록이 담긴 파일 경로.
            limit (Optional[int]): 처리할 최대 URL 수 
                - None 또는 0 이하: 모든 URL 처리
                - 양수: 지정된 개수만큼만 처리
            delay_sec (float): 각 URL 요청 사이의 지연 시간.
            extraction_mode (str): 추출 방식
                - sequential: 순차적으로 처리
                - balanced: 전체 URL 중 균등하게 분포하여 선택
                - per_date: 날짜별로 균등하게 분포하여 선택
            
        Returns:
            List[Dict[str, str]]: 추출된 모든 뉴스 데이터의 목록.
        """
        logger.info(f"URL 파일 처리 시작: {url_filepath}")
        
        # URL 파일 로드
        urls, source_metadata = self.load_urls_from_file(url_filepath)
        if not urls:
            logger.warning(f"파일에서 유효한 네이버 뉴스 URL을 로드하지 못했습니다: {url_filepath}")
            return []
        
        # self.query와 self.period를 URL 파일의 메타데이터로 업데이트 (파일명 생성 등에 영향)
        self.query = source_metadata.get("query", self.query)
        self.period = source_metadata.get("period", self.period)

        # URL 처리 및 결과 반환
        all_extracted_data, _ = self.process_urls(urls, source_metadata, limit, delay_sec, extraction_mode)
        
        return all_extracted_data


if __name__ == "__main__":
    # 예제 사용법
    # 1. 테스트용 URL 목록 JSON 파일 생성 (url_extractor.py 실행 결과물 사용 또는 수동 생성)
    sample_url_file_content = {
        "query": "AI",
        "period": "1주일",
        "collection_timestamp": datetime.now().strftime("%Y%m%d%H%M%S"),
        "total_urls_collected": 2,
        "urls": [
            {"type": "naver", "url": "https://n.news.naver.com/mnews/article/092/0002335297"}, # 예시 URL
            {"type": "naver", "url": "https://n.news.naver.com/mnews/article/001/0014719905"}  # 예시 URL
        ]
    }
    sample_json_filepath = "test_sample_urls.json"
    with open(sample_json_filepath, "w", encoding="utf-8") as f:
        json.dump(sample_url_file_content, f, indent=4)

    # 2. NaverNewsContentExtractor 인스턴스 생성 및 실행
    output_directory = "test_news_content_output"
    # 초기 query, period는 파일 로드 시 덮어쓰여질 수 있음
    extractor = NaverNewsContentExtractor(output_dir=output_directory, query="초기쿼리", period="초기기간") 
    
    # 파일 처리 (limit=2, delay=1.5초)
    extracted_news_list = extractor.process_url_file(sample_json_filepath, limit=2, delay_sec=1.5)
    
    # 3. 결과 확인
    if extracted_news_list:
        print(f"\n===== 총 {len(extracted_news_list)}개 뉴스 본문 추출 결과 (샘플) =====")
        for i, news in enumerate(extracted_news_list[:2], 1): # 최대 2개 샘플 출력
            print(f"\n--- 뉴스 {i} ---")
            print(f"  제목: {news.get('title', 'N/A')}")
            print(f"  언론사: {news.get('press', 'N/A')}")
            print(f"  날짜: {news.get('date', 'N/A')}")
            # print(f"  기자: {news.get('reporter', 'N/A')}")
            # content_preview = news.get('content', '')[:100] # 본문 미리보기
            # print(f"  본문 (처음 100자): {content_preview}...")
    else:
        print("추출된 뉴스 본문이 없습니다.")

    # 테스트 후 생성된 파일/디렉토리 정리 (선택적)
    # import shutil
    # if os.path.exists(sample_json_filepath): os.remove(sample_json_filepath)
    # if os.path.exists(output_directory): shutil.rmtree(output_directory)