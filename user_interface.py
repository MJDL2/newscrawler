# user_interface.py
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger('user_interface')

class NaverNewsUserInterface:
    """네이버 뉴스 크롤러 사용자 인터페이스 클래스"""
    
    def __init__(self):
        """인터페이스 초기화 및 기본 옵션 설정"""
        self.options = {
            'query': None,
            'output': 'news_data',
            'url_output': 'url_data',
            'period': '1m',
            'start_date': None,
            'end_date': None,
            'max_pages': 0,
            'sort': 'relevance',
            'news_type': 'all',
            'extract_content': False,
            'content_limit': 0,
            'extraction_mode': 'balanced',
            'request_delay': 1.0,
            'content_delay': 1.5,
            'daily_collect': False,
            'max_urls': 10,
            'url_type': 'all',
            'max_workers': 4, # 병렬 작업자 수 기본값 추가
        }
        
    def print_header(self):
        """헤더 출력"""
        print("\n" + "="*60)
        print(" " * 18 + "네이버 뉴스 크롤러 (대화형 설정)" + " " *18)
        print("="*60)
        
    def print_current_options(self):
        """현재 설정된 옵션들을 출력"""
        print("\n[ 현재 설정된 옵션 ]")
        for key, value in self.options.items():
            if value is not None:
                 if key == 'daily_collect' and not value:
                     continue
                 print(f"  - {key:<20}: {value}")
        print("-" * 30)
                
    def get_input(self, prompt: str, default_value: any = None) -> str:
        """
        사용자로부터 문자열 입력을 받음. 기본값이 있으면 함께 표시.
        """
        if default_value is not None:
            prompt_message = f"{prompt} (기본값: {str(default_value)}): "
        else:
            prompt_message = f"{prompt}: "
        
        user_input = input(prompt_message).strip()
        return user_input if user_input else str(default_value) if default_value is not None else ""
            
    def get_yes_no_input(self, prompt: str, default_is_yes: bool = True) -> bool:
        """
        사용자로부터 예(Y) 또는 아니오(N) 입력을 받음.
        """
        options_display = "(Y/n)" if default_is_yes else "(y/N)"
        prompt_message = f"{prompt} {options_display}: "
        
        user_input = input(prompt_message).strip().upper()
        
        if not user_input:
            return default_is_yes
            
        return user_input.startswith('Y')
    
    def set_query(self):
        """검색어 설정. 빈 입력 시 재시도."""
        while True:
            query_input = self.get_input("1. 검색어를 입력하세요 (필수)")
            if query_input:
                self.options['query'] = query_input
                break
            else:
                print("오류: 검색어는 반드시 입력해야 합니다.")
        
    def set_output_dirs(self):
        """데이터 저장 디렉토리 설정"""
        print("\n--- 데이터 저장 경로 설정 ---")
        self.options['output'] = self.get_input(
            "뉴스 본문 데이터 저장 디렉토리", 
            self.options['output']
        )
        self.options['url_output'] = self.get_input(
            "URL 목록 데이터 저장 디렉토리", 
            self.options['url_output']
        )
        
    def set_period(self):
        """검색 기간 설정. '직접 입력' 선택 시 날짜별 수집 여부도 질문."""
        print("\n--- 검색 기간 설정 ---")
        print("  1. 전체 기간 (all)")
        print("  2. 1시간 (1h)")
        print("  3. 1일 (1d)")
        print("  4. 1주일 (1w)")
        print("  5. 1개월 (1m) -- 기본값")
        print("  6. 3개월 (3m)")
        print("  7. 6개월 (6m)")
        print("  8. 1년 (1y)")
        print("  9. 직접 날짜 입력 (custom)")
        
        choice = self.get_input("2. 원하는 검색 기간을 선택하세요", "5")
        
        period_map = {
            "1": "all", "2": "1h", "3": "1d", "4": "1w",
            "5": "1m", "6": "3m", "7": "6m", "8": "1y", "9": "custom"
        }
        
        chosen_period = period_map.get(choice)
        if chosen_period:
            self.options['period'] = chosen_period
            if chosen_period == 'custom':
                print("\n날짜 형식은 YYYYMMDD 입니다 (예: 20240101).")
                while True:
                    start_date = self.get_input("시작일을 입력하세요 (예: 20230101)")
                    end_date = self.get_input("종료일을 입력하세요 (예: 20230131)")
                    try:
                        dt_start = datetime.strptime(start_date, "%Y%m%d")
                        dt_end = datetime.strptime(end_date, "%Y%m%d")
                        if dt_start <= dt_end:
                            self.options['start_date'] = start_date
                            self.options['end_date'] = end_date
                            break
                        else:
                            print("오류: 시작일이 종료일보다 늦을 수 없습니다. 다시 입력해주세요.")
                    except ValueError:
                        print("오류: 잘못된 날짜 형식입니다. YYYYMMDD 형식으로 다시 입력해주세요.")
            
            if chosen_period == 'custom':
                self.options['daily_collect'] = self.get_yes_no_input(
                    "해당 기간을 일별로 나누어 각각 수집하시겠습니까?", default_is_yes=False
                )
            else:
                self.options['daily_collect'] = False
                if chosen_period != 'custom':
                    self.options['start_date'] = None
                    self.options['end_date'] = None
        else:
            print("잘못된 선택입니다. 기본값(1개월)으로 설정합니다.")
            self.options['period'] = "1m"
            self.options['daily_collect'] = False
            
    def set_sort(self):
        """정렬 방식 설정"""
        print("\n--- 정렬 방식 설정 ---")
        print("  1. 관련도순 (relevance) -- 기본값")
        print("  2. 최신순 (recent)")
        print("  3. 오래된순 (oldest)")
        
        choice = self.get_input("3. 원하는 정렬 방식을 선택하세요", "1")
        sort_map = {"1": "relevance", "2": "recent", "3": "oldest"}
        self.options['sort'] = sort_map.get(choice, "relevance")
            
    def set_news_type(self):
        """뉴스 유형 설정"""
        print("\n--- 뉴스 유형 설정 ---")
        print("  1. 전체 (all) -- 기본값")
        print("  2. 포토 (photo)")
        print("  3. 동영상 (video)")
        
        choice = self.get_input("4. 원하는 뉴스 유형을 선택하세요", "1")
        type_map = {"1": "all", "2": "photo", "3": "video"}
        self.options['news_type'] = type_map.get(choice, "all")
    
    def set_max_pages(self):
        """수집할 최대 페이지 수 설정"""
        print("\n--- 수집 페이지 수 설정 ---")
        while True:
            try:
                max_pages_str = self.get_input(
                    "5. 수집할 최대 페이지 수를 입력하세요 (0 입력 시 무제한)", 
                    str(self.options['max_pages'])
                )
                max_pages_val = int(max_pages_str)
                if max_pages_val >= 0:
                    self.options['max_pages'] = max_pages_val
                    break
                else:
                    print("오류: 페이지 수는 0 이상이어야 합니다.")
            except ValueError:
                print("오류: 숫자를 입력해야 합니다.")
                
    def set_max_urls(self):
        """URL 수집 제한 개수 설정"""
        print("\n--- URL 수집 제한 설정 ---")
        while True:
            try:
                max_urls_str = self.get_input(
                    "6. 수집할 URL 개수 제한을 입력하세요 (0=제한 없음, 양수=해당 개수만 수집)", 
                    str(self.options.get('max_urls', 10))
                )
                max_urls_val = int(max_urls_str)
                if max_urls_val >= 0:
                    self.options['max_urls'] = max_urls_val
                    if self.options.get('daily_collect', False):
                        self.options['daily_max_urls'] = max_urls_val
                    break
                else:
                    print("오류: URL 수집 제한은 0 이상이어야 합니다.")
            except ValueError:
                print("오류: 숫자를 입력해야 합니다.")
    
    def set_url_type(self):
        """URL 유형 설정"""
        print("\n--- URL 유형 설정 ---")
        print("  1. 모든 URL (all) -- 기본값")
        print("  2. 네이버 뉴스 URL만 (naver)")
        print("  3. 원본 기사 URL만 (original)")
        
        choice = self.get_input("7. 수집할 URL 유형을 선택하세요", "1")
        type_map = {"1": "all", "2": "naver", "3": "original"}
        self.options['url_type'] = type_map.get(choice, "all")
            
    def set_extract_content(self):
        """뉴스 본문 추출 여부 및 관련 제한 설정"""
        print("\n--- 뉴스 본문 추출 설정 ---")
        self.options['extract_content'] = self.get_yes_no_input(
            "8. 뉴스 본문을 추출하시겠습니까?", default_is_yes=True
        )
        
        if self.options['extract_content']:
            print("\n--- 본문 추출 제한 설정 ---")
            while True:
                try:
                    limit_str = self.get_input(
                        "추출할 본문 개수 제한을 입력하세요 (0=제한 없음, 양수=해당 개수만 추출)", 
                        str(self.options['content_limit'])
                    )
                    limit_val = int(limit_str)
                    if limit_val >= 0:
                        self.options['content_limit'] = limit_val
                        
                        if limit_val > 0:
                            print("\n--- 본문 추출 방식 설정 ---")
                            print("  1. 순차적 (sequential): 목록 앞에서부터 순서대로 추출")
                            print("  2. 균등 분포 (balanced): 전체 범위에서 균등하게 분포된 URL 선택 - 기본값")
                            print("  3. 날짜별 분포 (per_date): 날짜별로 균등하게 분포된 URL 선택")
                            
                            choice = self.get_input("본문 추출 방식을 선택하세요", "2")
                            mode_map = {"1": "sequential", "2": "balanced", "3": "per_date"}
                            self.options['extraction_mode'] = mode_map.get(choice, "balanced")
                        break
                    else:
                        print("오류: 본문 추출 제한은 0 이상이어야 합니다.")
                except ValueError:
                    print("오류: 숫자를 입력해야 합니다.")
                
    def set_delays(self):
        """요청 간 지연 시간 설정"""
        print("\n--- 요청 지연 시간 설정 (초 단위) ---")
        while True:
            try:
                delay_str = self.get_input(
                    "9. 각 페이지(URL 목록) 요청 사이의 지연 시간(초)", 
                    str(self.options['request_delay'])
                )
                delay_val = float(delay_str)
                if delay_val >= 0.1:
                    self.options['request_delay'] = delay_val
                    break
                else:
                    print("오류: 지연 시간은 0.1초 이상이어야 합니다.")
            except ValueError:
                print("오류: 숫자를 입력해야 합니다.")
        
        if self.options['extract_content']:
            while True:
                try:
                    content_delay_str = self.get_input(
                        "10. 각 뉴스 본문 요청 사이의 지연 시간(초)",
                        str(self.options['content_delay'])
                    )
                    content_delay_val = float(content_delay_str)
                    if content_delay_val >= 0.1:
                        self.options['content_delay'] = content_delay_val
                        break
                    else:
                        print("오류: 지연 시간은 0.1초 이상이어야 합니다.")
                except ValueError:
                    print("오류: 숫자를 입력해야 합니다.")

    def set_max_workers(self):
        """병렬 처리 작업자 수 설정"""
        print("\n--- 병렬 처리 작업자 수 설정 ---")
        while True:
            try:
                workers_str = self.get_input(
                    "11. 동시에 처리할 최대 날짜 수 (작업자 수, 1 이상)",
                    str(self.options['max_workers'])
                )
                workers_val = int(workers_str)
                if workers_val >= 1:
                    self.options['max_workers'] = workers_val
                    break
                else:
                    print("오류: 작업자 수는 1 이상이어야 합니다.")
            except ValueError:
                print("오류: 숫자를 입력해야 합니다.")
            
    def run_interactive(self) -> dict or None:
        """대화형 인터페이스를 순차적으로 실행하고 최종 옵션 딕셔셔니를 반환."""
        self.print_header()
        
        self.set_query()
        self.set_period()
        self.set_sort()
        self.set_news_type()
        self.set_max_pages()
        
        self.set_max_urls()
        self.set_url_type()
        
        self.set_extract_content()
        
        self.set_delays()
        self.set_max_workers() # 새로운 작업자 수 설정 추가
        self.set_output_dirs()
        
        self.print_current_options()
        
        if self.get_yes_no_input("\n위 설정으로 뉴스 크롤링을 실행하시겠습니까?", default_is_yes=True):
            logger.info("사용자 설정에 따라 크롤링을 시작합니다...")
            return self.options
        else:
            logger.info("사용자에 의해 크롤링 실행이 취소되었습니다.")
            return None

if __name__ == "__main__":
    ui_instance = NaverNewsUserInterface()
    final_selected_options = ui_instance.run_interactive()
    
    if final_selected_options:
        print("\n[ 최종 선택된 옵션 확인 ]")
        for option_key, option_value in final_selected_options.items():
            print(f"  {option_key}: {option_value}")
    else:
        print("\n대화형 설정이 취소되었거나 완료되지 않았습니다.")