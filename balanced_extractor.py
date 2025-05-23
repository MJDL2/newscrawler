"""
네이버 뉴스 균등 추출 유틸리티 모듈

날짜별로 URL과 본문을 균등하게 추출하기 위한 기능을 제공합니다.
"""

import logging
from typing import List, Dict, Any
import random
from datetime import datetime

logger = logging.getLogger('balanced_extractor')

def group_urls_by_date(urls: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    URL 목록을 날짜별로 그룹화
    
    Args:
        urls: URL 항목 목록. 각 항목은 'search_date' 키가 있어야 함
        
    Returns:
        Dict[str, List[Dict]]: 날짜별로 그룹화된 URL 딕셔너리
    """
    grouped = {}
    
    for url in urls:
        date = url.get('search_date')
        if not date:
            # search_date가 없다면 'unknown_date' 그룹에 추가
            date = 'unknown_date'
            
        if date not in grouped:
            grouped[date] = []
            
        grouped[date].append(url)
        
    return grouped


def extract_balanced_urls(all_urls: List[Dict[str, Any]], 
                          total_limit: int, 
                          extraction_mode: str = 'balanced') -> List[Dict[str, Any]]:
    """
    날짜별로 균등하게 URL을 선택
    
    Args:
        all_urls: URL 항목 목록
        total_limit: 추출할 최대 URL 수
        extraction_mode: 추출 방식 (sequential, balanced, per_date)
        
    Returns:
        List[Dict[str, Any]]: 선택된 URL 목록
    """
    if not all_urls:
        return []
    
    if extraction_mode == 'sequential' or total_limit <= 0:
        return all_urls[:total_limit] if total_limit > 0 else all_urls
    
    # 날짜별로 그룹화
    urls_by_date = group_urls_by_date(all_urls)
    if len(urls_by_date) <= 1:
        # 날짜 그룹이 1개 이하면 sequential과 동일하게 처리
        return all_urls[:total_limit] if total_limit > 0 else all_urls
    
    selected_urls = []
    
    if extraction_mode == 'balanced':
        # 균등 추출 모드: 각 날짜에서 균등하게 선택
        urls_per_date = max(1, total_limit // len(urls_by_date))
        
        # 1단계: 각 날짜에서 기본 할당량 선택
        for date, date_urls in urls_by_date.items():
            selected_urls.extend(date_urls[:urls_per_date])
        
        # 2단계: 남은 슬롯 채우기
        if len(selected_urls) < total_limit:
            remaining = []
            for date, date_urls in urls_by_date.items():
                if len(date_urls) > urls_per_date:
                    remaining.extend(date_urls[urls_per_date:])
            
            # 남은 URL 랜덤 셔플 (다양성을 위해)
            random.shuffle(remaining)
            selected_urls.extend(remaining[:total_limit - len(selected_urls)])
    
    elif extraction_mode == 'per_date':
        # 날짜별 독립 모드: 각 날짜를 독립적으로 처리
        date_limit = max(1, total_limit // len(urls_by_date))
        
        for date, date_urls in urls_by_date.items():
            selected_urls.extend(date_urls[:date_limit])
    
    return selected_urls[:total_limit] if total_limit > 0 else selected_urls
