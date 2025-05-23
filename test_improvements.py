"""
개선된 기능 테스트 스크립트
"""
import os
import sys
import json
from search_options import NaverNewsSearchOption
from url_extractor import NaverNewsURLExtractor

# 테스트 디렉토리 설정
TEST_DIR = "test_results"
os.makedirs(TEST_DIR, exist_ok=True)

def test_press_filter():
    """언론사 필터링 기능 테스트"""
    print("\n===== 언론사 필터링 테스트 =====")
    
    # 1. 일반 검색 URL 생성
    option_normal = NaverNewsSearchOption("AI")
    option_normal.set_period(NaverNewsSearchOption.PERIOD_1DAY)
    url_normal = option_normal.build_url()
    print(f"일반 검색 URL: {url_normal}")
    
    # 2. 언론사 필터링 매개변수 추가
    allowed_press = ["032", "025"]  # 032: 경향신문, 025: 중앙일보 (예시)
    press_params = option_normal.build_press_filter_params(allowed_press)
    print(f"언론사 필터 매개변수: {press_params}")
    
    # 3. 언론사 코드를 설정에 추가
    option_with_press = NaverNewsSearchOption("AI")
    option_with_press.set_period(NaverNewsSearchOption.PERIOD_1DAY)
    option_with_press.set_news_office(allowed_press)
    url_with_press = option_with_press.build_url()
    print(f"언론사 필터 URL: {url_with_press}")
    
    return url_normal, url_with_press

def test_duplicate_news_detection():
    """중복 기사 감지 알고리즘 테스트"""
    print("\n===== 중복 기사 감지 테스트 =====")
    
    # 테스트용 뉴스 데이터
    test_news = [
        {"title": "AI 기술의 발전과 미래 전망", "url": "https://example.com/news1"},
        {"title": "인공지능 기술의 발전과 미래 전망에 대한 고찰", "url": "https://example.com/news2"},  # 첫 번째와 유사
        {"title": "클라우드 컴퓨팅의 최신 동향", "url": "https://example.com/news3"},
        {"title": "AI 활용 사례: 헬스케어 분야", "url": "https://example.com/news4"},
        {"title": "AI 활용한 헬스케어 분야의 혁신", "url": "https://example.com/news5"},  # 네 번째와 유사
    ]
    
    print(f"원본 뉴스 건수: {len(test_news)}")
    for i, news in enumerate(test_news, 1):
        print(f"  {i}. {news['title']}")
    
    # 중복 필터링 실행
    extractor = NaverNewsURLExtractor(output_dir=TEST_DIR)
    filtered_news = extractor.filter_duplicate_news(test_news, title_key='title', threshold=0.7)
    
    print(f"\n중복 제거 후 뉴스 건수: {len(filtered_news)}")
    for i, news in enumerate(filtered_news, 1):
        print(f"  {i}. {news['title']}")
    
    # 유사도 테스트 추가
    print("\n제목 유사도 테스트:")
    title_pairs = [
        ("AI 기술의 발전", "인공지능 기술의 발전"),
        ("오늘의 날씨", "내일의 날씨 예보"),
        ("코로나19 백신 개발", "코로나19 백신 임상실험"),
        ("대선 후보 토론회", "대선 후보 토론회 일정"),
    ]
    
    for title1, title2 in title_pairs:
        similarity = extractor.is_similar_title(title1, title2, threshold=0.6)
        print(f"  '{title1}' vs '{title2}': {'유사함' if similarity else '다름'}")
    
    return filtered_news

if __name__ == "__main__":
    print("개선된 기능 테스트 시작")
    
    # 언론사 필터링 테스트
    normal_url, filtered_url = test_press_filter()
    
    # 중복 기사 감지 테스트
    filtered_news = test_duplicate_news_detection()
    
    print("\n테스트 완료!")
