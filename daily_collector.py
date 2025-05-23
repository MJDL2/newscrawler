# daily_collector.py
import os
import logging
from datetime import datetime, timedelta
import time
import random
import json
import shutil
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("tqdm 패키지가 설치되어 있지 않습니다. 프로그레스 바 기능이 비활성화됩니다.")
    print("pip install tqdm 명령으로 설치할 수 있습니다.")

try:
    from main import run_crawler, get_period_text, get_sort_code, get_type_code
    from url_extractor import NaverNewsURLExtractor
    from news_content_extractor import NaverNewsContentExtractor
    import argparse
except ImportError as e:
    logging.error(f"main.py 또는 필요한 구성요소 임포트 실패: {e}")
    run_crawler = None
    NaverNewsURLExtractor = None
    NaverNewsContentExtractor = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger('daily_news_collector')

class NaverNewsDailyCollector:
    """네이버 뉴스 날짜별 수집 클래스"""

    def __init__(self, main_script_path: Optional[str] = None):
        self.stats = {
            "start_time": None,
            "end_time": None,
            "total_days_processed": 0,
            "completed_days": 0,
            "failed_days": 0,
            "total_collected_urls": 0,
            "total_collected_contents": 0,
            "errors": [],
            "daily_results": []
        }

    def parse_date(self, date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            logger.error(f"잘못된 날짜 형식: {date_str}. YYYYMMDD 형식을 사용해주세요.")
            return None

    def get_date_range(self, start_date_str: str, end_date_str: str) -> List[datetime]:
        start_date = self.parse_date(start_date_str)
        end_date = self.parse_date(end_date_str)

        if not start_date or not end_date:
            return []

        if start_date > end_date:
            logger.error(f"시작일({start_date_str})이 종료일({end_date_str})보다 늦을 수 없습니다.")
            return []

        date_range: List[datetime] = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        return date_range

    def _create_crawler_args_for_day(self, date_str: str, base_options: Dict[str, Any]) -> argparse.Namespace:
        args = argparse.Namespace()
        args.query = base_options.get("query", "지정되지않은쿼리")
        args.output = os.path.join(base_options.get("output", "news_data"), f"_daily_temp_{date_str}")
        args.url_output = os.path.join(base_options.get("url_output", "url_data"), f"_daily_temp_{date_str}")
        os.makedirs(args.output, exist_ok=True)
        os.makedirs(args.url_output, exist_ok=True)

        args.pages = base_options.get("max_pages", 0)
        args.sort = base_options.get("sort", "relevance")
        args.type = base_options.get("news_type", "all")
        args.delay = base_options.get("request_delay", 1.0)
        args.extract_content = base_options.get("extract_content", False)
        args.content_limit = base_options.get("content_limit", 0)
        args.content_delay = base_options.get("content_delay", 1.5)
        args.max_urls = base_options.get("daily_max_urls", 10)
        args.url_type = base_options.get("url_type", "all")
        args.period = "custom"
        args.start_date = date_str
        args.end_date = date_str
        args.extraction_mode = base_options.get("extraction_mode", "balanced")

        return args

    def collect_single_day(self, date_obj: datetime, base_options: Dict[str, Any]) -> Dict[str, Any]:
        date_str = date_obj.strftime("%Y%m%d")
        logger.info(f"===== {date_str} 날짜의 뉴스 수집 시작 =====")

        day_result = {
            "date": date_str,
            "success": False,
            "urls_collected_this_day": 0,
            "contents_extracted_this_day": 0,
            "error_message": None,
            "temp_output_dir": None,
            "temp_url_output_dir": None
        }

        if not run_crawler:
            day_result["error_message"] = "run_crawler 함수를 사용할 수 없어 수집을 진행할 수 없습니다."
            logger.error(day_result["error_message"])
            return day_result

        crawler_args = self._create_crawler_args_for_day(date_str, base_options)
        day_result["temp_output_dir"] = crawler_args.output
        day_result["temp_url_output_dir"] = crawler_args.url_output

        try:
            logger.info(f"{date_str}에 대해 run_crawler 실행. Query: '{crawler_args.query}', Output: '{crawler_args.output}'")
            crawl_execution_result = run_crawler(crawler_args)

            day_result["urls_collected_this_day"] = crawl_execution_result.get("urls_collected_count", 0)
            day_result["contents_extracted_this_day"] = crawl_execution_result.get("contents_extracted_count", 0)

            if day_result["urls_collected_this_day"] > 0 or day_result["contents_extracted_this_day"] > 0 :
                 day_result["success"] = True
            elif crawl_execution_result.get("urls_collected_count", -1) == 0 :
                 day_result["success"] = True
                 logger.info(f"{date_str} 날짜 뉴스 수집은 성공했으나, 실제 수집된 URL/본문은 없습니다.")
            else:
                 day_result["success"] = False
                 day_result["error_message"] = "run_crawler 실행은 완료되었으나, 명시적 성공/실패 판단 불가 또는 데이터 없음."


            logger.info(f"{date_str} 날짜 뉴스 수집 완료. "
                        f"URL: {day_result['urls_collected_this_day']}개, "
                        f"본문: {day_result['contents_extracted_this_day']}개")

        except Exception as e:
            error_msg = f"{date_str} 수집 중 예외 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            day_result["error_message"] = error_msg
            day_result["success"] = False

        return day_result

    def _aggregate_daily_outputs(self, daily_results: List[Dict[str, Any]],
                                 final_url_output_dir: str, final_news_output_dir: str,
                                 start_date_str: str, end_date_str: str, query: str):
        logger.info("모든 날짜의 결과물 통합 시작...")

        all_urls_data: List[Dict[str, Any]] = []
        all_news_content_data: List[Dict[str, Any]] = []

        for day_res in daily_results:
            if not day_res.get("success"):
                continue

            date_str = day_res["date"]
            temp_url_dir = day_res.get("temp_url_output_dir")
            temp_news_dir = day_res.get("temp_output_dir")

            if temp_url_dir and os.path.exists(temp_url_dir):
                for filename in os.listdir(temp_url_dir):
                    if filename.endswith(".json"):
                        filepath = os.path.join(temp_url_dir, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                all_urls_data.extend(data.get("urls", []))
                        except Exception as e:
                            logger.error(f"임시 URL 파일({filepath}) 로드/통합 중 오류: {e}")

            if temp_news_dir and os.path.exists(temp_news_dir):
                 for filename in os.listdir(temp_news_dir):
                    if filename.endswith(".json"):
                        filepath = os.path.join(temp_news_dir, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                all_news_content_data.extend(data.get("news_articles", []))
                        except Exception as e:
                            logger.error(f"임시 뉴스 본문 파일({filepath}) 로드/통합 중 오류: {e}")

        if all_urls_data:
            url_extractor_instance = NaverNewsURLExtractor(output_dir=final_url_output_dir)
            period_text = f"{start_date_str}~{end_date_str}"
            saved_url_path = url_extractor_instance.save_urls_to_file(
                all_urls_data,
                query=query,
                period=period_text,
                filename_prefix=f"TOTAL_daily_collected_urls_{start_date_str}_{end_date_str}"
            )
            if saved_url_path:
                logger.info(f"통합 URL {len(all_urls_data)}개 저장 완료: {saved_url_path}")
                self.stats["final_urls_file"] = saved_url_path


        if all_news_content_data:
            content_extractor_instance = NaverNewsContentExtractor(
                output_dir=final_news_output_dir,
                query=query,
                period=f"{start_date_str}~{end_date_str}"
            )

            batch_size = NaverNewsContentExtractor.MAX_NEWS_PER_FILE
            total_news_items = len(all_news_content_data)
            num_batches = (total_news_items + batch_size - 1) // batch_size

            current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            saved_news_files_paths = []

            for i in range(num_batches):
                batch_data = all_news_content_data[i*batch_size : (i+1)*batch_size]
                saved_file = content_extractor_instance.save_news_content_batch(
                    batch_data,
                    i * batch_size,
                    total_news_items,
                    current_timestamp
                )
                if saved_file:
                    saved_news_files_paths.append(saved_file)

            if saved_news_files_paths:
                logger.info(f"통합 뉴스 본문 {total_news_items}개, {len(saved_news_files_paths)}개 파일로 저장 완료.")
                self.stats["final_news_files"] = saved_news_files_paths

        logger.info("결과물 통합 완료.")

    def _cleanup_temp_dirs(self, daily_results: List[Dict[str, Any]]):
        logger.info("임시 디렉토리 정리 시작...")
        cleaned_count = 0
        for day_res in daily_results:
            for dir_key in ["temp_output_dir", "temp_url_output_dir"]:
                temp_dir = day_res.get(dir_key)
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir)
                        logger.debug(f"임시 디렉토리 삭제: {temp_dir}")
                        cleaned_count +=1
                    except Exception as e:
                        logger.error(f"임시 디렉토리({temp_dir}) 삭제 중 오류: {e}")
        if cleaned_count > 0:
            logger.info(f"{cleaned_count}개의 임시 디렉토리 정리 완료.")
        else:
            logger.info("정리할 임시 디렉토리가 없거나 이미 삭제되었습니다.")


    def collect_date_range(self, start_date_str: str, end_date_str: str,
                           options: Dict[str, Any],
                           random_day_delay: bool = True,
                           cleanup_temp: bool = True,
                           max_workers: int = 4) -> Optional[Dict[str, Any]]:
        date_objs_list = self.get_date_range(start_date_str, end_date_str)

        if not date_objs_list:
            logger.error("유효한 날짜 범위가 없어 수집을 시작할 수 없습니다.")
            return None

        self.stats["start_time"] = datetime.now().isoformat()
        self.stats["total_days_processed"] = len(date_objs_list)
        self.stats["completed_days"] = 0
        self.stats["failed_days"] = 0
        self.stats["total_collected_urls"] = 0
        self.stats["total_collected_contents"] = 0
        self.stats["errors"] = []
        self.stats["daily_results"] = []

        final_output_dir = options.get("output", "news_data")
        final_url_output_dir = options.get("url_output", "url_data")
        os.makedirs(final_output_dir, exist_ok=True)
        os.makedirs(final_url_output_dir, exist_ok=True)

        futures = []
        daily_results_ordered: List[Optional[Dict[str, Any]]] = [None] * len(date_objs_list)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i, date_obj_to_collect in enumerate(date_objs_list):
                future = executor.submit(self.collect_single_day, date_obj_to_collect, options)
                futures.append((i, future))

            if TQDM_AVAILABLE:
                pbar = tqdm(total=len(futures), desc="전체 날짜 수집 진행", unit="일")
            else:
                logger.info(f"총 {len(futures)}일의 뉴스 수집을 시작합니다.")

            for i, future in futures:
                try:
                    single_day_collection_result = future.result()
                    daily_results_ordered[i] = single_day_collection_result
                except Exception as e:
                    date_str_failed = date_objs_list[i].strftime("%Y%m%d")
                    error_msg = f"{date_str_failed} 날짜 처리 중 병렬 작업에서 예외 발생: {e}"
                    logger.error(error_msg, exc_info=True)
                    daily_results_ordered[i] = {
                        "date": date_str_failed,
                        "success": False,
                        "urls_collected_this_day": 0,
                        "contents_extracted_this_day": 0,
                        "error_message": error_msg,
                        "temp_output_dir": None,
                        "temp_url_output_dir": None
                    }
                finally:
                    if TQDM_AVAILABLE:
                        pbar.update(1)

            if TQDM_AVAILABLE:
                pbar.close()

        self.stats["daily_results"] = [res for res in daily_results_ordered if res is not None]

        for day_res in self.stats["daily_results"]:
            if day_res["success"]:
                self.stats["completed_days"] += 1
                self.stats["total_collected_urls"] += day_res["urls_collected_this_day"]
                self.stats["total_collected_contents"] += day_res["contents_extracted_this_day"]
            else:
                self.stats["failed_days"] += 1
                self.stats["errors"].append({
                    "date": day_res["date"],
                    "error": day_res["error_message"]
                })

        if self.stats["completed_days"] > 0:
            logger.info("모든 날짜 처리 완료. 결과 통합 중...")
            self._aggregate_daily_outputs(
                self.stats["daily_results"],
                final_url_output_dir,
                final_output_dir,
                start_date_str, end_date_str, options.get("query", "unknown_query")
            )
        else:
            logger.warning("성공적으로 처리된 날짜가 없어 결과물 통합을 건너뜁니다.")

        if cleanup_temp:
            logger.info("임시 디렉토리 정리 중...")
            self._cleanup_temp_dirs(self.stats["daily_results"])
        else:
            logger.info("임시 디렉토리 정리가 비활성화되어 유지됩니다.")

        self.stats["end_time"] = datetime.now().isoformat()
        start_dt = datetime.fromisoformat(self.stats["start_time"])
        end_dt = datetime.fromisoformat(self.stats["end_time"])
        self.stats["total_duration_seconds"] = (end_dt - start_dt).total_seconds()

        self.print_summary()
        self.save_stats(final_output_dir)

        return self.stats

    def print_summary(self):
        if not self.stats.get("start_time"):
            logger.warning("출력할 수집 통계가 없습니다.")
            return

        print("\n" + "="*60)
        print(" " * 20 + "일별 수집 결과 요약" + " " * 20)
        print("="*60)

        start_dt = datetime.fromisoformat(self.stats["start_time"])
        end_dt = datetime.fromisoformat(self.stats["end_time"])
        total_duration_sec = self.stats.get("total_duration_seconds", 0)

        hours, remainder = divmod(total_duration_sec, 3600)
        minutes, seconds = divmod(remainder, 60)

        print(f"시작 시간: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"종료 시간: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"총 소요 시간: {int(hours)}시간 {int(minutes)}분 {int(seconds)}초 ({total_duration_sec:.2f}초)")
        print(f"처리 대상 총 일수: {self.stats['total_days_processed']}일")
        print(f"성공적으로 처리된 일수: {self.stats['completed_days']}일")
        print(f"실패한 일수: {self.stats['failed_days']}일")
        print(f"전체 기간 수집된 URL 총계: {self.stats['total_collected_urls']}개")
        print(f"전체 기간 추출된 본문 총계: {self.stats['total_collected_contents']}개")

        if self.stats.get("final_urls_file"):
            print(f"통합 URL 저장 파일: {self.stats['final_urls_file']}")
        if self.stats.get("final_news_files"):
            print(f"통합 뉴스 본문 저장 파일(들): {', '.join(self.stats['final_news_files'])}")

        if self.stats.get("errors"):
            print("\n[ 발생 오류 목록 ]")
            for error_entry in self.stats["errors"]:
                print(f"  - 날짜: {error_entry['date']}, 오류: {error_entry['error']}")
        print("="*60)

    def save_stats(self, base_output_dir: str, filename: Optional[str] = None) -> Optional[str]:
        if not self.stats.get("start_time"):
            logger.warning("저장할 수집 통계가 없습니다.")
            return None

        stats_output_dir = os.path.join(base_output_dir, "collection_stats")
        os.makedirs(stats_output_dir, exist_ok=True)

        if not filename:
            start_date_str = self.stats.get("daily_results", [{}])[0].get("date", "unknown_start")
            end_date_str = self.stats.get("daily_results", [{}])[-1].get("date", "unknown_end")
            timestamp = datetime.fromisoformat(self.stats["start_time"]).strftime("%Y%m%d%H%M%S")
            filename = f"daily_collection_stats_{start_date_str}_to_{end_date_str}_{timestamp}.json"

        filepath = os.path.join(stats_output_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=4)
            logger.info(f"수집 통계 저장 완료: {filepath}")
            return filepath
        except IOError as e:
            logger.error(f"통계 파일 저장 중 오류 ({filepath}): {e}")
            return None