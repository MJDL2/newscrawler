"""
네이버 뉴스 검색 옵션 분석 및 URL 생성 모듈

이 모듈은 네이버 뉴스 검색의 다양한 옵션을 분석하고
검색 조건에 맞는 URL을 생성하는 기능을 제공합니다.
"""

import urllib.parse
from datetime import datetime, timedelta

class NaverNewsSearchOption:
    """네이버 뉴스 검색 옵션 클래스"""
    
    # 기본 검색 URL
    BASE_URL = "https://search.naver.com/search.naver"
    
    # 정렬 방식
    SORT_BY_RELEVANCE = "0"  # 관련도순
    SORT_BY_RECENT = "1"     # 최신순
    SORT_BY_OLDEST = "2"     # 오래된순
    
    # 기간 설정
    PERIOD_ALL = "0"        # 전체
    PERIOD_1HOUR = "1"      # 1시간
    PERIOD_1DAY = "2"       # 1일
    PERIOD_1WEEK = "3"      # 1주
    PERIOD_1MONTH = "4"     # 1개월
    PERIOD_3MONTHS = "5"    # 3개월
    PERIOD_6MONTHS = "6"    # 6개월
    PERIOD_1YEAR = "7"      # 1년
    PERIOD_CUSTOM = "8"     # 직접입력
    
    # 유형 설정
    TYPE_ALL = "0"          # 전체
    TYPE_PHOTO = "1"        # 포토
    TYPE_VIDEO = "2"        # 동영상
    TYPE_PRINT = "3"        # 지면기사
    TYPE_PRESS_RELEASE = "4"  # 보도자료
    TYPE_AUTO_GENERATED = "5"  # 자동생성기사
    
    # 서비스 영역
    SERVICE_ALL = "0"       # 전체
    SERVICE_MOBILE_MAIN = "1"  # 모바일 메인 언론사
    SERVICE_PC_MAIN = "2"   # PC 메인 언론사
    
    def __init__(self, query):
        """
        네이버 뉴스 검색 옵션 객체 초기화
        
        Args:
            query (str): 검색할 키워드
        """
        self.query = query
        self.sort = self.SORT_BY_RELEVANCE  # 기본값: 관련도순
        self.period = self.PERIOD_ALL       # 기본값: 전체기간
        self.start_date = None              # 직접입력 시작일
        self.end_date = None                # 직접입력 종료일
        self.news_type = self.TYPE_ALL      # 기본값: 전체유형
        self.service_area = self.SERVICE_ALL  # 기본값: 전체 서비스 영역
        self.news_office = []               # 선택된 언론사 목록
        self.reporter = None                # 기자명
        
    def set_sort(self, sort_type):
        """
        정렬 방식 설정
        
        Args:
            sort_type (str): 정렬 방식 코드
        """
        self.sort = sort_type
        return self
    
    def set_period(self, period_type, start_date=None, end_date=None):
        """
        기간 설정
        
        Args:
            period_type (str): 기간 코드
            start_date (str, optional): 시작일(YYYYMMDD 형식), 직접입력시 필요
            end_date (str, optional): 종료일(YYYYMMDD 형식), 직접입력시 필요
        """
        self.period = period_type
        
        if period_type == self.PERIOD_CUSTOM:
            if not start_date or not end_date:
                raise ValueError("직접입력 기간을 선택할 경우 시작일과 종료일을 반드시 지정해야 합니다.")
            self.start_date = start_date
            self.end_date = end_date
        else:
            # 직접입력이 아닌 경우 시작일/종료일 초기화
            self.start_date = None
            self.end_date = None
            
        return self
        
    def set_news_type(self, news_type):
        """
        뉴스 유형 설정
        
        Args:
            news_type (str): 뉴스 유형 코드
        """
        self.news_type = news_type
        return self
    
    def set_service_area(self, service_area):
        """
        서비스 영역 설정
        
        Args:
            service_area (str): 서비스 영역 코드
        """
        self.service_area = service_area
        return self
    
    def set_news_office(self, news_office_list):
        """
        특정 언론사 설정
        
        Args:
            news_office_list (list): 언론사 코드 목록
        """
        self.news_office = news_office_list
        return self
        
    def build_press_filter_params(self, allowed_press_list=None):
        """
        언론사 필터링 매개변수 구성
        
        Args:
            allowed_press_list (list, optional): 허용할 언론사 코드 목록
            
        Returns:
            dict: 언론사 필터 매개변수
        """
        if not allowed_press_list:
            return {}
        
        # 언론사 필터링 설정
        press_param = {
            'mynews': '1',
            'news_office_checked': ','.join(allowed_press_list)
        }
        return press_param
    
    def set_reporter(self, reporter_name):
        """
        기자명 설정
        
        Args:
            reporter_name (str): 기자 이름
        """
        self.reporter = reporter_name
        return self
    
    def _get_period_param(self):
        """기간 설정 파라미터 생성"""
        if self.period == self.PERIOD_ALL:
            return "p:all"
        elif self.period == self.PERIOD_1HOUR:
            return "p:1h"
        elif self.period == self.PERIOD_1DAY:
            return "p:1d"
        elif self.period == self.PERIOD_1WEEK:
            return "p:1w"
        elif self.period == self.PERIOD_1MONTH:
            return "p:1m"
        elif self.period == self.PERIOD_3MONTHS:
            return "p:3m"
        elif self.period == self.PERIOD_6MONTHS:
            return "p:6m"
        elif self.period == self.PERIOD_1YEAR:
            return "p:1y"
        elif self.period == self.PERIOD_CUSTOM:
            # 직접입력일 경우 시작일과 종료일 포함
            return f"p:from{self.start_date}to{self.end_date}"
        
        # 기본값: 전체기간
        return "p:all"
    
    def build_url(self, safe_search: bool = True):
        """
        설정된 옵션으로 네이버 뉴스 검색 URL 생성
        
        Args:
            safe_search (bool): 안전한 검색 URL 생성 여부 (True=기본값)
            
        Returns:
            str: 네이버 뉴스 검색 URL
        """
        # 기본 파라미터
        params = {
            "where": "news",
            "query": self.query,
            "sm": "tab_opt",
            "sort": self.sort,
            "photo": "0" if self.news_type == self.TYPE_ALL else "1" if self.news_type == self.TYPE_PHOTO else "0",
            "field": "0",
            "pd": self.period,
            "ds": self.start_date if self.start_date else "",
            "de": self.end_date if self.end_date else "",
            "docid": "",
            "related": "0",
            "mynews": "0",
            "office_type": "0",
            "office_section_code": "0",
            "news_office_checked": ",".join(self.news_office) if self.news_office else "",
            "nso": f"so:r,{self._get_period_param()},a:all", # 여기서 self.sort 대신 'r'(관련도순)이 기본으로 들어감. 필요시 수정.
                                                            # 만약 sort가 nso 파라미터의 so: 다음 값과 연동되어야 한다면,
                                                            # sort_map = {'0': 'r', '1': 's', '2': 'o'} 같은 매핑 필요
                                                            # 현재 코드는 sort는 별도 파라미터, nso는 so:r로 고정된 상태.
            "is_sug_officeid": "0",
            "office_category": "",
            "service_area": "",
        }
        
        # 네이버 검색 도구의 보안 측면을 고려한 URL 생성 (필요시)
        if safe_search:
            # URL 인코딩된 파라미터 문자열 생성
            query_string = urllib.parse.urlencode(params)
            # 완성된 URL 반환
            return f"{self.BASE_URL}?{query_string}"
        else:
            # 단순 URL 생성 (고급 옵션 또는 디버깅용)
            # 실제 검색 시 문제가 있을 수 있으므로 기본적으로 비활성화
            query_params = []
            for key, value in params.items():
                if value:  # 값이 있는 파라미터만 포함
                    query_params.append(f"{key}={value}")
            return f"{self.BASE_URL}?{'&'.join(query_params)}"

    @staticmethod
    def get_date_str(days_ago=0, format="%Y%m%d"):
        """
        특정 날짜의 문자열 반환
        
        Args:
            days_ago (int): 오늘 기준 이전 일수
            format (str): 날짜 형식
            
        Returns:
            str: 날짜 문자열
        """
        target_date = datetime.now() - timedelta(days=days_ago)
        return target_date.strftime(format)