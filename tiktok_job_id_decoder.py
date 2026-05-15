#!/usr/bin/env python3
"""
TikTok / ByteDance Job ID Decoder

lifeattiktok.com 공고 URL의 Job ID에서 게시 시점을 추정하는 도구.

원리:
  TikTok Job ID는 Twitter Snowflake 방식의 64-bit 정수 ID로 추정됨.
  - 상위 ~42 bit: timestamp (milliseconds)
  - 하위 22 bit: machine ID + sequence
  ID를 22 bit 우측 시프트하면 ms 단위 timestamp가 나옴.

  단, ByteDance epoch을 모르므로 절대 시각은 직접 계산 불가.
  → 대신 게시일이 확정된 reference ID를 calibration point로 사용.

Calibration:
  Reference: 7634297575580092677 = 2026-04-30 03:00 Pacific Time
  (사용자가 직접 확인한 시점)

사용법:
  python3 tiktok_job_id_decoder.py 7566369771879958789
  python3 tiktok_job_id_decoder.py 7566369771879958789 7632085581813827845 ...
  python3 tiktok_job_id_decoder.py --sort 7566... 7632... 7634...
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone

# ---- Calibration ---------------------------------------------------------
# Reference ID와 게시 시각.
# 검증: LinkedIn에서 "17시간 전" 표시로 확인 (2026-05-14 23:18 ET 시점 기준)
# Job: Product Operations Project Intern Pangle (Advertisement Team) - 2026 Start (BS/MS)
REFERENCE_ID = 7639514228211124533
REFERENCE_TIME_PT = datetime(2026, 5, 14, 3, 18, 38)  # Pacific Time
PT_OFFSET_HOURS = -7  # PDT (서머타임). PST(겨울)이면 -8.

# Snowflake bit 분배 가정
SEQUENCE_AND_MACHINE_BITS = 22
# --------------------------------------------------------------------------


def get_reference_time_utc() -> datetime:
    """Reference 시각을 UTC로 변환."""
    return (REFERENCE_TIME_PT - timedelta(hours=PT_OFFSET_HOURS)).replace(
        tzinfo=timezone.utc
    )


def decode_job_id(job_id: int) -> dict:
    """
    Job ID에서 게시 시점을 추정해서 dict로 반환.

    Returns:
        {
            'job_id': int,
            'posted_utc': datetime (UTC, tz-aware),
            'posted_pt': datetime (Pacific Time, naive),
            'days_ago': float,
            'hours_ago': float,
        }
    """
    ref_time_utc = get_reference_time_utc()
    diff = REFERENCE_ID - job_id
    ms_diff = diff >> SEQUENCE_AND_MACHINE_BITS  # 하위 22 bit 제거

    posted_utc = ref_time_utc - timedelta(milliseconds=ms_diff)
    posted_pt = posted_utc.replace(tzinfo=None) + timedelta(hours=PT_OFFSET_HOURS)
    delta = ref_time_utc - posted_utc
    days_ago = delta.total_seconds() / 86400
    hours_ago = delta.total_seconds() / 3600

    return {
        'job_id': job_id,
        'posted_utc': posted_utc,
        'posted_pt': posted_pt,
        'days_ago': days_ago,
        'hours_ago': hours_ago,
    }


def format_relative(days_ago: float) -> str:
    """상대 시간을 사람이 읽기 좋게 포맷."""
    if days_ago < 0:
        return f"미래 ({-days_ago:.1f}일 후) — reference보다 최신"
    if days_ago < 1:
        hours = days_ago * 24
        if hours < 1:
            return f"{hours * 60:.0f}분 전"
        return f"{hours:.1f}시간 전"
    if days_ago < 14:
        return f"{days_ago:.1f}일 전"
    if days_ago < 60:
        return f"{days_ago:.0f}일 전 (≈ {days_ago / 7:.1f}주 전)"
    return f"{days_ago:.0f}일 전 (≈ {days_ago / 30:.1f}개월 전)"


def print_single(result: dict) -> None:
    """단일 ID 결과를 보기 좋게 출력."""
    print(f"\nJob ID: {result['job_id']}")
    print(f"  게시일 (Pacific Time): {result['posted_pt'].strftime('%Y-%m-%d %H:%M')}")
    print(f"  게시일 (UTC):          {result['posted_utc'].strftime('%Y-%m-%d %H:%M')}")
    print(f"  상대 시각:             {format_relative(result['days_ago'])}")


def print_table(results: list, label_map: dict | None = None) -> None:
    """여러 ID 결과를 표 형태로 출력 (최신순 정렬)."""
    label_map = label_map or {}
    results_sorted = sorted(results, key=lambda r: -r['job_id'])

    print(f"\n{'Job ID':<22} {'게시일 (PT)':<20} {'상대 시각':<25} 메모")
    print("=" * 100)
    for r in results_sorted:
        label = label_map.get(r['job_id'], '')
        print(
            f"{r['job_id']:<22} "
            f"{r['posted_pt'].strftime('%Y-%m-%d %H:%M'):<20} "
            f"{format_relative(r['days_ago']):<25} "
            f"{label}"
        )


def parse_input(raw: str) -> tuple[int, str]:
    """
    입력 문자열 parse. 다음 형식 모두 지원:
      "7566369771879958789"
      "7566369771879958789:Product Strategist MBA"
      "https://lifeattiktok.com/search/7566369771879958789"
      "https://lifeattiktok.com/search/7566369771879958789?spread=XXX"
    Returns: (job_id, label)
    """
    raw = raw.strip()
    label = ''

    # "ID:label" 형식
    if ':' in raw and not raw.startswith('http'):
        parts = raw.split(':', 1)
        raw = parts[0].strip()
        label = parts[1].strip()

    # URL 형식
    if 'lifeattiktok.com' in raw:
        # /search/ 뒤의 숫자 추출
        after = raw.split('/search/')[-1]
        raw = after.split('?')[0].split('/')[0].strip()

    if not raw.isdigit():
        raise ValueError(f"Job ID로 해석 불가: {raw}")

    return int(raw), label


def main() -> int:
    parser = argparse.ArgumentParser(
        description='TikTok lifeattiktok.com 공고 ID로 게시일 추정',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python3 tiktok_job_id_decoder.py 7566369771879958789
  python3 tiktok_job_id_decoder.py 7566369771879958789 7632085581813827845
  python3 tiktok_job_id_decoder.py "7566369771879958789:Product Strategist"
  python3 tiktok_job_id_decoder.py https://lifeattiktok.com/search/7566369771879958789

stdin에서 읽기 (한 줄에 하나씩):
  cat ids.txt | python3 tiktok_job_id_decoder.py -
        """
    )
    parser.add_argument(
        'ids',
        nargs='*',
        help='Job ID 또는 lifeattiktok.com URL. 여러 개면 자동으로 표 형태 정렬.'
    )
    parser.add_argument(
        '--stdin',
        '-',
        action='store_true',
        dest='from_stdin',
        help='stdin에서 한 줄에 하나씩 읽기'
    )
    args = parser.parse_args()

    inputs = list(args.ids)
    # 단일 인자가 "-"면 stdin으로 처리
    if inputs == ['-'] or args.from_stdin:
        inputs = [line for line in sys.stdin.read().splitlines() if line.strip()]

    if not inputs:
        parser.print_help()
        return 1

    results = []
    label_map = {}
    for raw in inputs:
        try:
            job_id, label = parse_input(raw)
        except ValueError as e:
            print(f"⚠️  건너뜀: {e}", file=sys.stderr)
            continue
        result = decode_job_id(job_id)
        results.append(result)
        if label:
            label_map[job_id] = label

    if not results:
        print("처리할 ID가 없습니다.", file=sys.stderr)
        return 1

    if len(results) == 1:
        print_single(results[0])
    else:
        print_table(results, label_map)

    print(f"\n[Calibration] Reference ID: {REFERENCE_ID}")
    print(f"              = {REFERENCE_TIME_PT.strftime('%Y-%m-%d %H:%M')} Pacific Time")
    return 0


if __name__ == '__main__':
    sys.exit(main())
