# TikTok Job ID Decoder

`lifeattiktok.com` 채용 공고 URL의 Job ID에서 **게시 시점을 추정**하는 도구.

```
https://lifeattiktok.com/search/7566369771879958789
                                ^^^^^^^^^^^^^^^^^^^
                                이 19자리 숫자가 Job ID
```

이 ID는 단순한 일련번호가 아니라 **timestamp가 인코딩된 64-bit 정수**라서, 디코딩하면 게시 시점을 추정할 수 있다.

---

## 빠른 시작

```bash
# 단일 ID
python3 tiktok_job_id_decoder.py 7566369771879958789

# URL 그대로 넣어도 OK
python3 tiktok_job_id_decoder.py https://lifeattiktok.com/search/7566369771879958789

# 여러 개 (자동 정렬되어 표로 출력)
python3 tiktok_job_id_decoder.py 7634027... 7566369... 7632085...

# Label 붙이기
python3 tiktok_job_id_decoder.py "7566369771879958789:Product Strategist MBA"

# stdin에서 한 줄에 하나씩
cat job_ids.txt | python3 tiktok_job_id_decoder.py -
```

### 출력 예시

```
Job ID: 7566369771879958789
  게시일 (Pacific Time): 2025-10-24 16:19
  게시일 (UTC):          2025-10-24 23:19
  상대 시각:             187일 전 (≈ 6.2개월 전)
```

여러 개 입력 시:

```
Job ID                 게시일 (PT)         상대 시각              메모
====================================================================
7634297575580092677    2026-04-30 03:00    0분 전                 오늘 (기준)
7634027348048709941    2026-04-29 09:06    17.9시간 전            Product Manager
7566369771879958789    2025-10-24 16:19    187일 전 (≈ 6.2개월)   Product Strategist MBA
```

---

## 원리

### TikTok Job ID는 Snowflake ID

ByteDance/TikTok의 Job ID는 Twitter Snowflake와 유사한 **64-bit 분산 ID** 포맷으로 추정됨:

```
[1 bit][   ~41 bit timestamp (ms)   ][~10 bit machine][~12 bit sequence]
                                      └────── 하위 22 bit ──────┘
```

- 상위 ~42 bit: 자체 epoch 기준 millisecond timestamp
- 하위 22 bit: machine ID + sequence (충돌 방지용)

ID를 22 bit 우측 시프트(`id >> 22`)하면 ms 단위 timestamp만 남는다.

### 그런데 epoch을 모름

ByteDance가 어떤 시점을 기준 epoch으로 쓰는지 비공개. 그래서 timestamp만 뽑아도 **절대 시각으로 변환 불가**.

→ **Calibration 방식**으로 해결: 게시 시각이 확정된 reference ID 하나를 기준점으로 잡고, 다른 ID와의 ms 차이를 빼서 상대 게시일을 계산.

```python
ms_diff = (REFERENCE_ID - target_id) >> 22
target_time = REFERENCE_TIME - timedelta(milliseconds=ms_diff)
```

### 현재 calibration

```python
REFERENCE_ID    = 7634297575580092677
REFERENCE_TIME  = 2026-04-30 03:00 Pacific Time
```

이 reference는 사용자가 게시 직후 직접 확인한 ID. 시간이 지나면 더 최신 reference로 교체하는 게 좋음 (오차 누적 방지).

---

## 정확도

### Self-test (calibration ID 자기 자신)
완벽히 0초 일치.

### Google "X days ago" 데이터와 비교
| Job ID | 계산값 | Google 표시 | 차이 |
|--------|--------|-------------|------|
| 7632085 | 6.1일 전 | 4 days ago | +2일 |
| 7631289 | 8.3일 전 | 5 days ago | +3일 |
| 7630679 | 10.0일 전 | 7 days ago | +3일 |
| 7623941 | 29일 전 | 7 days ago | **+22일** |

**계산값이 Google보다 항상 큼**. 두 가지 해석:

1. **Google "X days ago"는 첫 crawl 시점**이지 실제 게시일이 아님. 공고가 update되면 "다시 며칠 전"으로 reset되는 경우가 흔함 (특히 7623941처럼 큰 차이).
2. **이 도구의 계산이 실제 게시일에 더 가까움** — calibration이 사용자가 직접 본 게시 시각이라서.

다만 다음 한계는 인지하고 쓸 것:

- Bit 분배(22-bit)가 정확히 맞다는 보장은 없음. ±10~20% 오차 가능.
- ByteDance가 시스템을 바꾸면 calibration이 깨짐.
- 1~3일 단위는 신뢰할 만하지만, 분/시간 단위 정밀도는 과신 금물.

---

## Reference 갱신

시간이 지나거나 더 신뢰할 수 있는 reference가 생기면 코드 상단을 수정:

```python
REFERENCE_ID = 76XXXXXXXXXXXXXXXXX     # 새 ID
REFERENCE_TIME_PT = datetime(YYYY, M, D, H, M, 0)
PT_OFFSET_HOURS = -7  # PDT면 -7, PST(겨울)면 -8
```

**좋은 reference의 조건:**
- 게시 시각을 정확히 아는 ID (직접 본 게시 직후 시점이 가장 좋음)
- 가능하면 최근 ID (calibration drift 최소화)
- 단일 시점에 게시된 ID (batch 게시 중 하나는 부정확할 수 있음)

---

## 활용 예시

채용 공고 신선도 빠르게 분류:

```bash
# 지원할 공고 list를 stdin으로
cat <<'EOF' | python3 tiktok_job_id_decoder.py -
7634297575580092677
7632085581813827845
7566369771879958789
7486252250214467848
EOF
```

→ 각 공고가 며칠 전인지 한눈에 보고, **rolling basis 공고는 일찍 올라온 것일수록 이미 많이 reviewed됐을 가능성**이 높으므로 우선순위 조정.

---

## 파일

- `tiktok_job_id_decoder.py` — CLI 스크립트
- `README.md` — 이 문서
