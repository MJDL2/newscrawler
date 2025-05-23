# 네이버 뉴스 크롤러 프로젝트 구조

## 프로젝트 개요

**프로젝트명**: 네이버 뉴스 크롤러  
**버전**: v.g(3) - 병렬 처리 지원 버전  
**최종 업데이트**: 2025-05-23  
**프로젝트 위치**: `C:\MYCLAUDE_PROJECT\claude\news_crawler_ver.g (3)`

## 핵심 기능

1. **네이버 뉴스 검색 및 URL 수집**
2. **뉴스 본문 추출 및 저장**
3. **날짜별/기간별 수집 지원**
4. **병렬 처리를 통한 성능 최적화**
5. **다양한 추출 모드 지원** (순차적, 균등분포, 날짜별분포)

## 아키텍처 구조

### 핵심 모듈

```
news_crawler_ver.g(3)/
├── main.py                     # 메인 실행 스크립트, CLI 인터페이스
├── user_interface.py           # 대화형 사용자 인터페이스
├── search_options.py           # 네이버 검색 옵션 처리
├── url_extractor.py            # URL 수집 및 중복 필터링
├── news_content_extractor.py   # 뉴스 본문 추출
├── balanced_extractor.py       # 균등분포 추출 로직
├── daily_collector.py          # 날짜별 수집 및 병렬 처리
└── test_improvements.py        # 테스트 및 검증 스크립트
```

### 데이터 저장소

```
├── url_data/                   # 수집된 URL 데이터
├── news_data/                  # 추출된 뉴스 본문 데이터
│   └── collection_stats/       # 수집 통계 데이터
└── test_results/              # 테스트 결과 데이터
```

## 데이터 흐름

```
[네이버 검색] → [URL 수집] → [중복 필터링] → [본문 추출] → [JSON 저장]
     ↓              ↓              ↓              ↓              ↓
search_options   url_extractor  url_extractor  news_content   JSON 파일
                                              _extractor
```

### 병렬 처리 흐름 (daily_collector.py)

```
[날짜 범위 분할] → [병렬 작업 생성] → [동시 실행] → [결과 통합] → [임시파일 정리]
      ↓                ↓               ↓             ↓              ↓
   date_range     ThreadPoolExecutor  각 날짜별    결과물 통합    임시 디렉토리
                                      독립 수집                    정리
```

## 주요 클래스 및 함수

### NaverNewsSearchOption (search_options.py)
- 네이버 검색 옵션 구성
- 기간, 정렬, 언론사 필터링 지원

### NaverNewsURLExtractor (url_extractor.py)
- URL 수집 및 페이지네이션 처리
- 제목 유사도 기반 중복 필터링
- 최대 수집량 제한 지원

### NaverNewsContentExtractor (news_content_extractor.py)
- 뉴스 본문 추출
- 다양한 추출 모드 지원
- 배치 단위 저장 처리

### NaverNewsDailyCollector (daily_collector.py)
- 날짜별 수집 관리
- 병렬 처리 (ThreadPoolExecutor)
- 진행상황 표시 (tqdm)

### NaverNewsUserInterface (user_interface.py)
- 대화형 인터페이스 제공
- 사용자 설정 검증
- 직관적인 옵션 설명

## 설정 및 옵션

### CLI 주요 옵션
- `--period`: 검색 기간 (all, 1h, 1d, 1w, 1m, 3m, 6m, 1y, custom)
- `--max-urls`: URL 수집 제한
- `--content-limit`: 본문 추출 제한
- `--extraction-mode`: 추출 방식 (sequential, balanced, per_date)
- `--max-workers`: 병렬 처리 작업자 수
- `--daily-collect`: 날짜별 수집 활성화

### 추출 모드 상세
- **sequential**: 순차적 추출 (기본값)
- **balanced**: 전체 범위에서 균등분포 추출
- **per_date**: 날짜별 균등분포 추출

## 출력 데이터 형식

### URL 데이터 (url_data/*.json)
```json
{
  "metadata": {
    "query": "검색어",
    "period": "기간",
    "extraction_timestamp": "수집시간",
    "total_items": 100
  },
  "urls": [
    {
      "title": "기사제목",
      "url": "기사URL",
      "press": "언론사",
      "date": "게시일"
    }
  ]
}
```

### 뉴스 데이터 (news_data/*.json)
```json
{
  "metadata": {
    "query": "검색어",
    "period": "기간",
    "extraction_timestamp": "추출시간",
    "batch_range": "1-20",
    "total_items_in_source": 100
  },
  "news_articles": [
    {
      "title": "기사제목",
      "url": "기사URL",
      "press": "언론사",
      "date": "게시일",
      "content": "본문내용"
    }
  ]
}
```

## 성능 특성

### 병렬 처리 개선사항 (2025-05-23)
- **ThreadPoolExecutor 도입**: 여러 날짜 동시 처리
- **프로그레스 바**: tqdm 기반 진행상황 표시
- **메모리 최적화**: 날짜별 독립 처리로 메모리 효율성 향상
- **오류 격리**: 개별 날짜 실패가 전체에 영향 미치지 않음

### 권장 설정
- **일반 사용**: `--max-workers 4`, `--max-urls 300`, `--content-limit 100`
- **대량 수집**: `--max-workers 8`, `--max-urls 0`, `--content-limit 0`
- **빠른 테스트**: `--max-workers 2`, `--max-urls 50`, `--content-limit 20`

## 의존성

### 필수 패키지
- `requests`: HTTP 요청 처리
- `beautifulsoup4`: HTML 파싱
- `concurrent.futures`: 병렬 처리 (Python 3.2+ 기본 제공)

### 선택적 패키지
- `tqdm`: 프로그레스 바 표시
- `difflib`: 제목 유사도 계산 (Python 기본 제공)

## 확장성

### 모듈 확장 포인트
1. **새로운 추출 모드 추가**: `balanced_extractor.py` 확장
2. **언론사별 파싱 규칙**: `news_content_extractor.py`에 언론사별 로직 추가
3. **데이터 후처리**: 수집된 데이터 분석/가공 모듈 추가
4. **GUI 인터페이스**: 웹 또는 데스크톱 GUI 개발

### 성능 최적화 가능 영역
1. **비동기 네트워크 요청**: `aiohttp` 도입 검토
2. **데이터베이스 연동**: SQLite/PostgreSQL 저장소 구축
3. **캐싱 시스템**: Redis 등을 활용한 중복 방지
4. **분산 처리**: 다중 서버 환경 지원
