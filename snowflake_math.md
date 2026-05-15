# TikTok Job ID 디코딩 — 수학식 정리

`lifeattiktok.com` 공고 URL의 19자리 Job ID에서 게시 시각을 역산하는 수학적 원리.

---

## 1. Job ID의 비트 구조 (가정)

Job ID는 **64-bit 정수**이고, Twitter Snowflake와 유사한 방식으로 다음과 같이 구성된다고 가정한다:

$$
\underbrace{\text{ID}}_{\text{64 bit}} = \underbrace{T}_{\text{상위 42 bit}} \cdot 2^{22} + \underbrace{R}_{\text{하위 22 bit}}
$$

| 구간 | 비트 수 | 역할 |
|------|--------|------|
| $T$ | 상위 ~42 bit | ByteDance 자체 epoch 기준 millisecond timestamp |
| $R$ | 하위 22 bit | machine ID + sequence (충돌 방지) |

$R$의 범위: $0 \le R < 2^{22} = 4{,}194{,}304$

---

## 2. Timestamp 추출 (비트 시프트)

ID에서 timestamp $T$만 꺼내려면 하위 22 bit를 잘라내면 된다. 즉 $2^{22}$로 나눈 몫(floor division):

$$
T = \left\lfloor \frac{\text{ID}}{2^{22}} \right\rfloor = \text{ID} \gg 22
$$

여기서 $\gg$는 **우측 비트 시프트** 연산자. 양의 정수에서는 $\div 2^{22}$의 floor와 정확히 같다.

```python
T = job_id >> 22
```

---

## 3. ByteDance epoch을 모르는 문제

$T$를 구해도 이건 "ByteDance 자체 epoch 기준 ms"이지 Unix epoch이 아니다. 실제 시각으로 변환하려면:

$$
t_{\text{actual}} = E + T \cdot 1\text{ms}
$$

여기서 $E$는 ByteDance epoch — 공개되지 않음. 그래서 직접 변환 불가.

→ **차분(difference) 방식**으로 우회한다.

---

## 4. Calibration: 두 ID의 차이로 시간 간격 계산

게시 시각이 알려진 reference ID $\text{ID}_{\text{ref}}$ (시각 $t_{\text{ref}}$)를 기준으로, target ID와의 timestamp 차이:

$$
\Delta T_{\text{ms}} = T_{\text{ref}} - T_{\text{target}} = \frac{\text{ID}_{\text{ref}} - \text{ID}_{\text{target}}}{2^{22}}
$$

epoch $E$가 양쪽에서 똑같이 빠지므로 **상쇄되어 사라진다**. 이게 calibration 방식의 핵심.

$$
\boxed{\;\Delta T_{\text{ms}} = \frac{\text{ID}_{\text{ref}} - \text{ID}_{\text{target}}}{2^{22}}\;}
$$

---

## 5. 게시 시각 복원

Target ID의 게시 시각:

$$
t_{\text{target}} = t_{\text{ref}} - \Delta T_{\text{ms}} \cdot 1\text{ms}
$$

며칠 전인지 환산:

$$
\text{days ago} = \frac{\Delta T_{\text{ms}}}{86{,}400{,}000}
$$

분모는 $1000 \times 60 \times 60 \times 24 = 86{,}400{,}000$ (하루의 ms 수).

---

## 6. 핵심 공식 한 줄

$$
\boxed{\;t_{\text{target}} = t_{\text{ref}} - \frac{\text{ID}_{\text{ref}} - \text{ID}_{\text{target}}}{2^{22}}\text{ ms}\;}
$$

Python 코드:

```python
ms_diff = (REFERENCE_ID - target_id) >> 22
posted  = reference_time - timedelta(milliseconds=ms_diff)
```

---

## 7. 실제 계산 예시

**7566369771879958789 — Product Strategist Intern (MBA)**

Reference (LinkedIn 검증):
- $\text{ID}_{\text{ref}} = 7{,}639{,}514{,}228{,}211{,}124{,}533$
- $t_{\text{ref}}$ = 2026-05-14 03:18 Pacific Time (Pangle 공고, LinkedIn "17시간 전" 검증)

**Step 1. ID 차이**

$$
7{,}639{,}514{,}228{,}211{,}124{,}533 - 7{,}566{,}369{,}771{,}879{,}958{,}789 = 73{,}144{,}456{,}331{,}165{,}744
$$

**Step 2. $2^{22}$로 나누기**

$$
\Delta T_{\text{ms}} = \frac{73{,}144{,}456{,}331{,}165{,}744}{4{,}194{,}304} \approx 17{,}439{,}007{,}488\text{ ms}
$$

**Step 3. 일수 환산**

$$
\frac{17{,}439{,}007{,}488}{86{,}400{,}000} \approx 201.84\text{ 일}
$$

**Step 4. 날짜 역산**

$$
\text{2026-05-14 03:18 PT} - 201.84\text{ 일} \approx \text{2025-10-24 07:08 PT}
$$

→ 약 **6.7개월 전** (202일 전)에 게시된 공고.

---

## 8. 가정과 한계

이 공식은 다음 가정에 의존한다:

1. **하위 22 bit가 machine + sequence** — Twitter Snowflake 표준. ByteDance가 다르게 분배했으면 `22`를 다른 값으로 (21, 23 등) 교체해야 함.
2. **Timestamp 단위가 millisecond** — microsecond라면 결과가 1000배 어긋남.
3. **Reference ID의 게시 시각이 정확** — 부정확하면 모든 target ID 결과가 같은 만큼 shift됨.

가장 중요한 변수는 3번이다. **Reference는 직접 게시 직후 본 ID로 잡을 것.**

---

## 9. 검증 결과

Self-test (reference 자기 자신): 0초 일치 ✅

Google "X days ago" 데이터와 비교 시, 계산값이 항상 Google 표시보다 큰 값이 나옴. 두 가지 해석:

1. Google은 **첫 crawl 시점** 또는 **마지막 update 시점** 기준이라 실제 게시일과 다름. 공고가 한 번 update되면 "다시 며칠 전"으로 reset됨.
2. Bit 분배가 정확히 22-bit이 아닐 가능성도 약간 있음.

→ 일/주 단위 정확도는 충분히 신뢰 가능. 분/시간 단위는 과신 금물.

---

## 10. 참고: 비트 연산이 익숙하지 않다면

`x >> 22`는 다음과 동일 (양의 정수일 때):

$$
x \gg 22 = \left\lfloor \frac{x}{2^{22}} \right\rfloor = \left\lfloor \frac{x}{4{,}194{,}304} \right\rfloor
$$

비트 단위로 보면, 64-bit 숫자의 **하위 22 bit를 잘라내고** 상위 42 bit만 남기는 연산이다.

```
ID (64-bit binary):  [ 42-bit timestamp ][ 22-bit machine+seq ]
ID >> 22:            [ 0...0 ][ 42-bit timestamp ]
```

이 timestamp는 ByteDance epoch부터의 ms 누적값이다.
