# main.py
import os
import logging
import argparse
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

from search_options import NaverNewsSearchOption
from url_extractor import NaverNewsURLExtractor
from news_content_extractor import NaverNewsContentExtractor

try:
    from user_interface import NaverNewsUserInterface
    has_ui_modules = True
except ImportError:
    has_ui_modules = False
    NaverNewsUserInterface = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger('main_crawler_script')

def check_environment():
    """환경 검사 및 필요한 패키지 확인"""
    missing_packages = []
    
    try:
        import requests
        logger.info("✓ requests 패키지 확인됨")
    except ImportError:
        missing_packages.append("requests")
        logger.error("✗ requests 패키지를 찾을 수 없습니다.")
    
    try:
        import bs4
        logger.info("✓ bs4 (BeautifulSoup4) 패키지 확인됨")
    except ImportError:
        missing_packages.append("beautifulsoup4")
        logger.error("✗ bs4 (BeautifulSoup4) 패키지를 찾을 수 없습니다.")
    
    try:
        import selenium
        logger.info("✓ selenium 패키지 확인됨 (선택 사항)")
    except ImportError:
        logger.warning("ℹ selenium 패키지가 설치되어 있지 않습니다. 일부 고급 기능이 제한될 수 있습니다.")
    
    output_dirs = ["news_data", "url_data"]
    for d in output_dirs:
        if not os.path.exists(d):
            logger.info(f"ℹ {d} 디렉토리가 없어 생성합니다.")
            os.makedirs(d, exist_ok=True)
    
    import sys
    logger.info(f"ℹ 시스템 기본 인코딩: {sys.getdefaultencoding()}")
    
    if missing_packages:
        logger.error(f"다음 필수 패키지를 설치하세요: {', '.join(missing_packages)}")
        logger.error("pip install " + " ".join(missing_packages))
        return False
    
    return True

def parse_arguments() -> argparse.Namespace:
    """
    명령행 인자 파싱
    
    Returns:
        argparse.Namespace: 파싱된 인자 객체
    """
    parser = argparse.ArgumentParser(description='네이버 뉴스 크롤러')
    
    parser.add_argument('query', nargs='?', help='검색할 키워드')
    parser.add_argument('--output', default='news_data', help='뉴스 데이터 저장 디렉토리 (기본값: news_data)')
    parser.add_argument('--url-output', default='url_data', help='URL 데이터 저장 디렉토리 (기본값: url_data)')
    parser.add_argument('--pages', type=int, default=0, help='수집할 페이지 수 (0=무제한, 기본값: 0)')
    parser.add_argument('--max-urls', type=int, default=0, 
                      help='수집할 최대 URL 개수 (0=제한 없음, 기본값: 0)')
    parser.add_argument('--url-type', choices=['all', 'naver', 'original'], default='all', 
                      help='수집할 URL 유형 (all=모두, naver=네이버뉴스만, original=원본기사만, 기본값: all)')
    parser.add_argument('--sort', choices=['relevance', 'recent', 'oldest'], default='relevance', 
                        help='정렬 방식 (관련도순, 최신순, 오래된순, 기본값: relevance)')
    parser.add_argument('--period', choices=['all', '1h', '1d', '1w', '1m', '3m', '6m', '1y', 'custom'], 
                        default='1m', help='검색 기간 (기본값: 1m)')
    parser.add_argument('--start-date', help='시작일 (YYYYMMDD 형식, --period=custom 필요)')
    parser.add_argument('--end-date', help='종료일 (YYYYMMDD 형식, --period=custom 필요)')
    parser.add_argument('--type', choices=['all', 'photo', 'video', 'print', 'press_release', 'auto'], 
                        default='all', help='뉴스 유형 (기본값: all)')
    parser.add_argument('--delay', type=float, default=1.0, 
                        help='URL 요청 간 지연 시간(초) (기본값: 1.0)')
    parser.add_argument('--extract-content', action='store_true', 
                        help='뉴스 본문 추출 여부')
    parser.add_argument('--content-limit', type=int, default=0, 
                        help='추출할 뉴스 본문 수 제한 (0=전체 URL 처리, 기본값: 0)')
    parser.add_argument('--content-delay', type=float, default=1.5, 
                        help='본문 추출 시 요청 간 지연 시간(초) (기본값: 1.5)')
    parser.add_argument('--verbose', '-v', action='store_true', help='상세 로그 출력')
    parser.add_argument('--extraction-mode', choices=['sequential', 'balanced', 'per_date'], default='balanced',
                     help='본문 추출 방식 (sequential=순차적, balanced=날짜별 균등, per_date=날짜별 독립)')
    
    if has_ui_modules:
        parser.add_argument('--interactive', '-i', action='store_true', help='대화형 인터페이스 사용')
    
    parser.add_argument('--daily-collect', action='store_true', 
                        help='날짜별 수집 수행 (기간 내 일별로 나누어 수집, --period=custom 필요)')
    
    parser.add_argument('--max-workers', type=int, default=4,
                        help='날짜별 수집 시 사용할 최대 작업자(스레드) 수 (기본값: 4)') # max_workers 추가
        
    return parser.parse_args()

def get_sort_code(sort_arg: str) -> str:
    """인자로 받은 정렬 방식을 코드로 변환"""
    sort_map = {
        'relevance': NaverNewsSearchOption.SORT_BY_RELEVANCE,
        'recent': NaverNewsSearchOption.SORT_BY_RECENT,
        'oldest': NaverNewsSearchOption.SORT_BY_OLDEST
    }
    return sort_map.get(sort_arg.lower(), NaverNewsSearchOption.SORT_BY_RELEVANCE)

def get_period_code(period_arg: str) -> str:
    """인자로 받은 기간을 코드로 변환"""
    period_map = {
        'all': NaverNewsSearchOption.PERIOD_ALL,
        '1h': NaverNewsSearchOption.PERIOD_1HOUR,
        '1d': NaverNewsSearchOption.PERIOD_1DAY,
        '1w': NaverNewsSearchOption.PERIOD_1WEEK, 
        '1m': NaverNewsSearchOption.PERIOD_1MONTH,
        '3m': NaverNewsSearchOption.PERIOD_3MONTHS,
        '6m': NaverNewsSearchOption.PERIOD_6MONTHS,
        '1y': NaverNewsSearchOption.PERIOD_1YEAR,
        'custom': NaverNewsSearchOption.PERIOD_CUSTOM
    }
    return period_map.get(period_arg.lower(), NaverNewsSearchOption.PERIOD_1MONTH)

def get_type_code(type_arg: str) -> str:
    """인자로 받은 뉴스 유형을 코드로 변환"""
    type_map = {
        'all': NaverNewsSearchOption.TYPE_ALL,
        'photo': NaverNewsSearchOption.TYPE_PHOTO,
        'video': NaverNewsSearchOption.TYPE_VIDEO,
        'print': NaverNewsSearchOption.TYPE_PRINT,
        'press_release': NaverNewsSearchOption.TYPE_PRESS_RELEASE,
        'auto': NaverNewsSearchOption.TYPE_AUTO_GENERATED
    }
    return type_map.get(type_arg.lower(), NaverNewsSearchOption.TYPE_ALL)

def get_period_text(period_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """기간 코드와 날짜를 기반으로 사람이 읽을 수 있는 기간 텍스트 생성"""
    if period_code == NaverNewsSearchOption.PERIOD_ALL: return "전체기간"
    if period_code == NaverNewsSearchOption.PERIOD_1HOUR: return "1시간"
    if period_code == NaverNewsSearchOption.PERIOD_1DAY: return "1일"
    if period_code == NaverNewsSearchOption.PERIOD_1WEEK: return "1주일"
    if period_code == NaverNewsSearchOption.PERIOD_1MONTH: return "1개월"
    if period_code == NaverNewsSearchOption.PERIOD_3MONTHS: return "3개월"
    if period_code == NaverNewsSearchOption.PERIOD_6MONTHS: return "6개월"
    if period_code == NaverNewsSearchOption.PERIOD_1YEAR: return "1년"
    if period_code == NaverNewsSearchOption.PERIOD_CUSTOM and start_date and end_date:
        return f"{start_date}~{end_date}"
    return "알수없는기간"

def run_crawler(crawl_options: argparse.Namespace) -> Dict[str, Any]:
    """
    크롤러 실행 로직. daily_collector 에서도 호출 가능하도록 수정.
    
    Args:
        crawl_options: 명령행 인자 또는 이에 상응하는 옵션을 담은 Namespace 객체.
                       필수 필드: query, output, url_output, pages, sort, period, 
                                 start_date, end_date, type, delay, extract_content, 
                                 content_limit, content_delay.

    Returns:
        Dict[str, Any]: 수집 결과를 담은 딕셔너리.
                        {
                            "urls_collected_count": int,
                            "contents_extracted_count": int,
                            "collected_urls": List[Dict[str,str]], # 수집된 URL 목록
                            "extracted_news_data": List[Dict[str,str]] # 추출된 뉴스 데이터 목록
                        }
    """
    results: Dict[str, Any] = {
        "urls_collected_count": 0,
        "contents_extracted_count": 0,
        "collected_urls": [],
        "extracted_news_data": []
    }

    if not crawl_options.query:
        logger.error("검색어가 지정되지 않았습니다.")
        return results
        
    os.makedirs(crawl_options.output, exist_ok=True)
    os.makedirs(crawl_options.url_output, exist_ok=True)
    
    search_option = NaverNewsSearchOption(crawl_options.query)
    search_option.set_sort(get_sort_code(crawl_options.sort))
    search_option.set_news_type(get_type_code(crawl_options.type))
    
    period_code = get_period_code(crawl_options.period)
    if period_code == NaverNewsSearchOption.PERIOD_CUSTOM:
        if not crawl_options.start_date or not crawl_options.end_date:
            logger.error("--period=custom 사용 시 --start-date와 --end-date를 반드시 지정해야 합니다.")
            return results
        search_option.set_period(period_code, crawl_options.start_date, crawl_options.end_date)
    else:
        search_option.set_period(period_code)
    
    search_url = search_option.build_url()
    logger.info(f"생성된 검색 URL: {search_url}")
    
    url_extractor = NaverNewsURLExtractor(output_dir=crawl_options.url_output)
    
    logger.info("뉴스 URL 수집 시작...")
    
    url_type_filter = None
    if hasattr(crawl_options, 'url_type') and crawl_options.url_type != 'all':
        url_type_filter = crawl_options.url_type
        
    collected_urls = url_extractor.collect_from_search(
        search_url, 
        max_pages=crawl_options.pages, 
        delay_sec=crawl_options.delay,
        max_urls=crawl_options.max_urls if hasattr(crawl_options, 'max_urls') else 0,
        url_type_filter=url_type_filter
    )
    results["collected_urls"] = collected_urls
    results["urls_collected_count"] = len(collected_urls)
    
    if not collected_urls:
        logger.warning("수집된 뉴스 URL이 없습니다.")
        return results
    
    period_text_for_file = get_period_text(period_code, crawl_options.start_date, crawl_options.end_date)
    
    json_filepath = url_extractor.save_urls_to_file(
        collected_urls, 
        query=crawl_options.query, 
        period=period_text_for_file 
    )
    
    logger.info(f"===== '{crawl_options.query}' URL 수집 결과 ({period_text_for_file}) =====")
    logger.info(f"총 수집된 URL 수: {len(collected_urls)}")
    if json_filepath:
        logger.info(f"URL 데이터 저장 위치 (JSON): {json_filepath}")
    
    if crawl_options.extract_content:
        if not json_filepath:
            logger.error("URL 파일이 생성되지 않아 본문 추출을 진행할 수 없습니다.")
            return results

        logger.info("뉴스 본문 추출 시작...")
        content_extractor = NaverNewsContentExtractor(
            output_dir=crawl_options.output,
            query=crawl_options.query,
            period=period_text_for_file
        )
        
        extraction_mode = getattr(crawl_options, 'extraction_mode', 'sequential')
        
        extracted_news_data = content_extractor.process_url_file(
            json_filepath, 
            limit=crawl_options.content_limit if crawl_options.content_limit > 0 else None, 
            delay_sec=crawl_options.content_delay,
            extraction_mode=extraction_mode
        )
        results["extracted_news_data"] = extracted_news_data
        results["contents_extracted_count"] = len(extracted_news_data)
        
        if extracted_news_data:
            logger.info(f"총 {len(extracted_news_data)}개의 뉴스 본문 추출 완료.")
        else:
            logger.warning("추출된 뉴스 본문이 없습니다.")
    else:
        logger.info("뉴스 본문 추출 기능이 비활성화되어 있습니다. (--extract-content 사용)")
        
    return results


def run_interactive_mode() -> Optional[Dict[str, Any]]:
    """대화형 인터페이스 실행 후 사용자 옵션 반환"""
    if not NaverNewsUserInterface:
        logger.error("대화형 인터페이스 모듈을 로드할 수 없습니다.")
        return None
        
    ui = NaverNewsUserInterface()
    options = ui.run_interactive()
    
    if not options:
        logger.info("대화형 인터페이스에서 크롤링이 취소되었습니다.")
        return None
    return options

def main():
    if not check_environment():
        logger.error("필수 환경 검사를 통과하지 못했습니다. 프로그램을 종료합니다.")
        return
    
    args = parse_arguments()
    
    if has_ui_modules and getattr(args, 'interactive', False):
        interactive_options = run_interactive_mode()
        if not interactive_options:
            return

        for key, value in interactive_options.items():
            if hasattr(args, key):
                setattr(args, key, value)
            else:
                logger.warning(f"대화형 옵션 '{key}'는 argparse에 정의되지 않았습니다. 필요시 추가 고려.")

        args.daily_collect = interactive_options.get('daily_collect', False)
        # UI에서 설정된 max_workers 값을 args에 반영
        args.max_workers = interactive_options.get('max_workers', args.max_workers)

    if not args.query:
        logger.error("검색어가 지정되지 않았습니다. (CLI 또는 대화형 모드에서 입력 필요)")
        return

    if getattr(args, 'daily_collect', False):
        if args.period == 'custom' and args.start_date and args.end_date:
            try:
                from daily_collector import NaverNewsDailyCollector
            except ImportError:
                logger.error("NaverNewsDailyCollector 모듈을 찾을 수 없습니다. 날짜별 수집을 진행할 수 없습니다.")
                return

            logger.info("===== 날짜별 수집 모드 시작 =====")
            
            daily_collector_options = {
                "query": args.query,
                "output": args.output,
                "url_output": args.url_output,
                "max_pages": args.pages,
                "sort": args.sort,
                "news_type": args.type,
                "request_delay": args.delay,
                "extract_content": args.extract_content,
                "content_limit": args.content_limit,
                "content_delay": args.content_delay,
                "max_urls": args.max_urls,
                "daily_max_urls": getattr(args, "daily_max_urls", args.max_urls),
                "extraction_mode": args.extraction_mode,
            }
            
            collector = NaverNewsDailyCollector(main_script_path=__file__)
            stats = collector.collect_date_range(
                args.start_date, 
                args.end_date, 
                daily_collector_options,
                max_workers=args.max_workers # max_workers 인자 전달
            )
            pass
        else:
            logger.error("날짜별 수집(--daily-collect)은 --period=custom 과 --start-date, --end-date가 모두 지정되어야 합니다.")
            logger.info("일반 크롤링 모드로 전환합니다 (요청된 경우).")
            if not (args.period == 'custom' and args.start_date and args.end_date):
                 args.daily_collect = False
                 run_crawler_results = run_crawler(args)
                 logger.info(f"일반 크롤링 완료. URL {run_crawler_results['urls_collected_count']}건, 본문 {run_crawler_results['contents_extracted_count']}건 수집/추출.")

    if not getattr(args, 'daily_collect', False):
        logger.info("===== 일반 크롤링 모드 시작 =====")
        run_crawler_results = run_crawler(args)
        logger.info(f"일반 크롤링 완료. URL {run_crawler_results['urls_collected_count']}건, 본문 {run_crawler_results['contents_extracted_count']}건 수집/추출.")

if __name__ == "__main__":
    main()