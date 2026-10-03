#!/usr/bin/env python3
"""맞춤 이력서 점검기: 키워드 커버리지(ATS), AI 문체 흔적, 형식 위험, 금지 패턴.

사용법:
    python3 tools/resume_check.py resumes/01_xxx.md --keywords postings/01_xxx.txt

이력서 파일에 <!-- BEGIN --> ... <!-- END --> 표시가 있으면 그 사이(실제 제출 본문)만 검사한다.
"""
import argparse
import re
import statistics
import sys
from pathlib import Path

# 채용 AI·자소서 표절/생성 탐지기가 높은 점수를 주는 상투 표현.
# 구체적 사실 없이 쓰이면 생성형 문장으로 판정되기 쉽다.
CLICHES = [
    "열정", "시너지", "끊임없이", "도약", "이바지", "기여하고자", "역량을 발휘",
    "최선을 다하겠습니다", "성장할 수 있는", "가치를 창출", "혁신적인", "글로벌 인재",
    "다양한 경험을 바탕으로", "주도적으로", "소통 능력", "책임감을 가지고",
    "원동력", "밑거름", "발판으로", "한 단계 더", "무엇보다", "결론적으로",
    "뿐만 아니라", "이를 통해", "에 있어서", "를 바탕으로", "하는 데 기여",
]

# 숨김 텍스트·프롬프트 주입: 적발되면 즉시 탈락이나 부정행위로 처리된다. 절대 쓰지 않는다.
FORBIDDEN = [
    r"ignore (all |the )?previous", r"이전 지시", r"AI(는|에게).{0,10}(합격|높은 점수)",
    r"system prompt", r"<span[^>]*(display:\s*none|color:\s*#?fff)",
]

FORMAT_HAZARDS = {
    "이모지": re.compile("[\U0001F300-\U0001FAFF☀-➿]"),
    "특수 글머리(▶★◆①)": re.compile("[▶►★☆◆◇■□①-⑳]"),
    "탭 문자": re.compile("\t"),
}

PII = {
    "휴대폰 번호": re.compile(r"01[016789]-?\d{3,4}-?\d{4}"),
    "이메일": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
}


def body_of(text):
    m = re.search(r"<!-- BEGIN -->(.*?)<!-- END -->", text, re.S)
    return m.group(1) if m else text


def norm(s):
    return re.sub(r"[\s\-_/·]", "", s).lower()


def load_keywords(path):
    kws = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            kws.append(line)
    return kws


def sentences(text):
    prose = "\n".join(
        l for l in text.splitlines()
        if l.strip() and not l.lstrip().startswith(("#", "|", "-", "*")) and len(l.strip()) > 30
    )
    return [s.strip() for s in re.split(r"(?<=[.?!다])\s+", prose) if len(s.strip()) > 8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("resume")
    ap.add_argument("--keywords")
    args = ap.parse_args()

    body = body_of(Path(args.resume).read_text(encoding="utf-8"))
    nbody = norm(body)
    fail = False

    print(f"== {args.resume}")

    if args.keywords:
        kws = load_keywords(args.keywords)
        hit = [k for k in kws if norm(k) in nbody]
        miss = [k for k in kws if norm(k) not in nbody]
        pct = 100 * len(hit) // max(len(kws), 1)
        print(f"[ATS 키워드] {len(hit)}/{len(kws)} ({pct}%)")
        if miss:
            print("  누락:", ", ".join(miss))
        if pct < 70:
            print("  -> 70% 미만. 사실인 범위에서 누락 키워드를 본문에 넣을 것.")
            fail = True

    found = [(c, body.count(c)) for c in CLICHES if c in body]
    print(f"[AI 상투 표현] {sum(n for _, n in found)}회")
    for c, n in found:
        print(f"  '{c}' x{n}")
    if sum(n for _, n in found) > 3:
        fail = True

    sents = sentences(body)
    if len(sents) >= 5:
        lens = [len(s) for s in sents]
        cv = statistics.pstdev(lens) / statistics.mean(lens)
        endings = [re.sub(r"[^가-힣]", "", s)[-3:] for s in sents]
        top = max(set(endings), key=endings.count)
        share = endings.count(top) / len(endings)
        print(f"[문장 리듬] 문장 {len(sents)}개, 길이 변동계수 {cv:.2f} (0.35 이상 권장), "
              f"가장 흔한 어미 '{top}' {share:.0%} (60% 이하 권장)")
        starts = [s.split()[0] for s in sents if s.split()]
        rep = sorted({w for w in starts if starts.count(w) >= 3})
        if rep:
            print("  같은 말로 시작하는 문장 3회 이상:", ", ".join(rep))
        if cv < 0.35 or share > 0.6:
            fail = True

    for name, rx in FORMAT_HAZARDS.items():
        n = len(rx.findall(body))
        if n:
            print(f"[형식] {name} {n}개 -> 일부 ATS 파서가 깨뜨림. 일반 하이픈으로 교체 권장")

    for name, rx in PII.items():
        if rx.search(body):
            print(f"[개인정보] {name} 포함 -> 저장소 커밋 금지, 제출 직전 입력")
            fail = True

    for pat in FORBIDDEN:
        if re.search(pat, body, re.I):
            print(f"[금지] 숨김 텍스트/프롬프트 주입 의심 패턴: {pat}")
            fail = True

    print("결과:", "보완 필요" if fail else "통과")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
