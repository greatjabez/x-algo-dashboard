#!/usr/bin/env python3
"""X 알고리즘 대시보드 생성기 (표준 라이브러리만 사용)

xai-org/x-algorithm 저장소를 읽어서 site/index.html 을 만든다.
state/ 폴더에 커밋별 스냅샷과 지난 실행 결과를 저장해 변화를 비교한다.
"""
import argparse, datetime as dt, html, json, os, re, subprocess, sys

REPO_URL = "https://github.com/xai-org/x-algorithm"
HM = "home-mixer/params/param.rs"
VM = "vm-ranker/params.rs"
KST = dt.timezone(dt.timedelta(hours=9), "KST")
NEW_DAYS = 7
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")
SITE = os.path.join(HERE, "site")
SCHEMA = 2

# ---------------------------------------------------------------- parsing
PARAM_RE = re.compile(r'param!\(\s*(\w+)\s*,\s*([\w:<>]+)\s*,\s*"([^"]*)"\s*,\s*(.*?)\s*,?\s*\)\s*;', re.S)


def parse_params(text):
    out = {}
    if not text:
        return out
    for name, typ, key, val in PARAM_RE.findall(text):
        out[name] = {"t": typ, "v": " ".join(val.split())}
    return out


def count_param_macros(text):
    return len(re.findall(r"param!\(", text or ""))


def to_num(v):
    try:
        return float(v.replace("_", ""))
    except Exception:
        return None


def snapshot_from_texts(hm, vm):
    ph, pv = parse_params(hm), parse_params(vm)
    sw, wt, other = {}, {}, {}
    for src, ps in (("home-mixer", ph), ("vm-ranker", pv)):
        for n, p in ps.items():
            k = f"{src}:{n}"
            if p["t"] == "bool":
                sw[k] = p["v"] == "true"
            elif p["t"] in ("f64", "f32") and ("Weight" in n or "Boost" in n):
                wt[k] = to_num(p["v"])
            else:
                other[k] = p["v"]
    return {"switches": sw, "weights": wt, "other": other,
            "hm_macros": count_param_macros(hm), "vm_macros": count_param_macros(vm)}


# ---------------------------------------------------------------- git
def git(src, *args):
    r = subprocess.run(["git", "-C", src, *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def ensure_source(src):
    if os.path.isdir(os.path.join(src, ".git")):
        subprocess.run(["git", "-C", src, "fetch", "-q", "origin"], check=False)
        subprocess.run(["git", "-C", src, "reset", "-q", "--hard", "origin/HEAD"], check=False)
    else:
        subprocess.run(["git", "clone", "-q", REPO_URL, src], check=True)


def commits(src):
    out = git(src, "log", "--format=%H%x1f%cI%x1f%s%x1f%an")
    res = []
    for line in out.strip().splitlines():
        h, d, s, a = line.split("\x1f")
        res.append({"sha": h, "date": d, "msg": s, "author": a})
    return res  # newest first


def kst(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)


# ---------------------------------------------------------------- texts
def load_json(name):
    """번역 파일 읽기. 없거나 깨져도 빈 dict 를 돌려줘서 영어 원문으로 보이게 한다."""
    try:
        d = json.load(open(os.path.join(HERE, name), encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _strmap(d):
    return {k: v for k, v in (d or {}).items() if isinstance(k, str) and isinstance(v, str) and v.strip()} if isinstance(d, dict) else {}


_KO = load_json("ko_names.json")
KO_SW = {}
for _k, _v in (_KO.get("switch") or {}).items() if isinstance(_KO.get("switch"), dict) else []:
    if isinstance(_v, str) and _v.strip():
        KO_SW[_k] = (_v, "")
    elif isinstance(_v, (list, tuple)) and _v and isinstance(_v[0], str) and _v[0].strip():
        KO_SW[_k] = (_v[0], _v[1] if len(_v) > 1 and isinstance(_v[1], str) else "")
KO_W = _strmap(_KO.get("weight"))
KO_ST = _strmap(_KO.get("setting"))
KO_NOTE = _strmap(load_json("ko_notices.json").get("items"))

KEY = {  # 이름: (한글 이름, 한 줄 설명)
    "EnableRanking": ("점수 순위 매기기", "VM 랭커로 글 점수를 매김"),
    "EnableRankerVmRank": ("랭커 VM 순위", "Phoenix 요청에 VM 순위를 넣어 다시 매김"),
    "EnablePageDecodeRerank": ("페이지 디코드 재정렬", "페이지 디코드로 타임라인 칸 순서를 다시 정함"),
    "EnableFairShareRanking": ("공정 배분 순위", "점수 계산 전에 후보를 출처별로 비율 맞춰 남김"),
    "EnableAuthorDiversity": ("작성자 다양성", "같은 작성자 글이 몰리지 않게 점수를 낮춤"),
    "DppEnabled": ("유사 글 분산 (DPP)", "DPP로 비슷한 글이 몰리지 않게 고름"),
    "VMRankerSendEngagementIneligible": ("유도 라벨 전달", "답글·공유·클릭 유도 라벨을 랭커에 전달"),
    "ExcludeIneligibleEngagementHeads": ("유도 점수 제외", "그 라벨이 있으면 해당 참여 점수를 빼고 계산"),
    "EnableNewUserSoftNsfwFilter": ("신규 NSFW 필터", "신규 계정 For You에서 소프트 NSFW 글을 걸러냄"),
    "EnableNewUserMinEngagementFilter": ("신규 참여 필터", "신규·복귀 계정에게 참여가 낮은 글을 걸러냄"),
    "EnableVideoCarousel": ("영상 캐러셀", "For You 홈에 영상 캐러셀을 넣음"),
    "EnableVideoCarouselMoeSource": ("캐러셀 MoE 소스", "캐러셀 후보를 Phoenix MoE에서 가져옴"),
    "EnableVideoCarouselMoeOnly": ("캐러셀 MoE만 사용", "캐러셀 후보를 MoE 소스만 씀"),
    "EnableVideoCarouselHighRiskFilter": ("고위험 영상 제외", "고위험 브랜드 세이프티 영상을 캐러셀에서 제외"),
    "EnableVideoCarouselMediumRiskFilter": ("중위험 영상 제외", "중위험 브랜드 세이프티 영상을 캐러셀에서 제외"),
    "EnableVideoCarouselSeenFilter": ("본 영상 제외", "이미 본 영상을 캐러셀에서 제외"),
    "EnableTeacherScoreSideEffect": ("AI 학습 점수", "똑똑하지만 느린 큰 모델이 매긴 점수를 저장해 뒀다가, 작고 빠른 모델이 그걸 따라 하도록 학습시키는 데 써요. 지금 노출에는 직접 영향이 없어요"),
    "EnableUnderTheHood": ("타임라인 추적", "타임라인 추적 요청을 허용"),
    "EnableUnderTheHoodSetting": ("추적 사용자 설정", "타임라인 추적을 사용자 설정에 따름"),
    "EnableUnderTheHoodFrame": ("추적 화면 표시", "타임라인 추적 화면을 피드 맨 위에 넣음"),
    "EnableXaiVfClient": ("xAI 필터 클라이언트", "어느 노출 필터 클라이언트를 쓸지 고름 (필터 자체 ON/OFF 아님)"),
    "EnablePhoenixSource": ("Phoenix 후보 소스", "Phoenix 모델에서 추천 후보를 가져옴"),
    "EnableSimclustersSource": ("SimClusters 후보 소스", "관심사 클러스터에서 추천 후보를 가져옴"),
    "EnableTweetMixerSource": ("TweetMixer 후보 소스", "TweetMixer에서 추천 후보를 가져옴"),
}

CAT_TIP = {
    "ranking": "후보 글에 점수를 매기고 순서를 다시 정하는 기능이에요. 같은 사람·비슷한 글이 몰리지 않게 섞는 것도 여기 들어가요",
    "spam": "답글·공유·클릭을 유도하는 낚시 글에 감점 라벨을 붙이거나, 신규 계정에게 보여줄 글을 거르는 기능이에요",
    "video": "영상 캐러셀(영상만 모아 보여주는 칸)과 영상 후보를 고르는 기능이에요. 홈 피드 영상 가중치와는 별개예요",
    "filter": "추천 후보 중에서 보여주면 안 되는 글을 걸러내는 기능이에요",
    "source": "추천할 후보 글을 어느 모델·저장소에서 가져올지 정하는 기능이에요",
    "exp": "타임라인 추적, 로그, AI 학습용 기록처럼 노출 순위에 직접 영향이 없는 기능이 대부분이에요",
    "other": "광고 배치 등 위 분류에 안 들어가는 나머지 기능이에요",
}
WTIP = {
    "ShareViaCopyLinkWeight": "누군가 글 링크를 복사해서 다른 곳(카톡·커뮤니티 등)에 퍼갈 것 같은 확률",
    "__mutual": "서로 팔로우하는 사람이 내 원글에 답글을 달 것 같은 확률. 일반 답글 점수에 맞팔 보너스가 더해져요",
    "ReplyWeight": "글을 본 사람이 답글을 달 것 같은 확률",
    "QuoteWeight": "글을 본 사람이 인용해서 자기 글로 올릴 것 같은 확률",
    "ShareViaDmWeight": "글을 DM(쪽지)으로 다른 사람에게 보낼 것 같은 확률",
    "FollowAuthorWeight": "글을 보고 작성자를 팔로우할 것 같은 확률",
    "ShareWeight": "공유 버튼으로 공유할 것 같은 확률 (DM·링크 복사 말고 일반 공유)",
    "RetweetWeight": "글을 재게시(리트윗)할 것 같은 확률",
    "FavoriteWeight": "글에 좋아요를 누를 것 같은 확률",
    "ClickWeight": "글을 눌러서 상세 화면으로 들어갈 것 같은 확률",
    "OpenLinkWeight": "글 안의 외부 링크를 열 것 같은 확률",
    "PhotoExpandWeight": "사진을 눌러 크게 볼 것 같은 확률",
    "QuotedClickWeight": "인용된 원래 글을 눌러볼 것 같은 확률",
    "PostUnexploredWeight": "아직 노출 데이터가 적은 새 글에 주는 작은 탐색 보너스",
}
NEGTIP = {
    "ReportWeight": "이 글을 신고할 것 같은 확률에 곱하는 감점. 실제 신고 1번이 좋아요 수백 개를 지운다는 뜻은 아니에요",
    "MuteAuthorWeight": "이 글을 보고 작성자를 뮤트할 것 같은 확률에 곱하는 감점",
    "NotInterestedWeight": "\"관심 없음\"을 누를 것 같은 확률에 곱하는 감점",
    "BlockAuthorWeight": "이 글을 보고 작성자를 차단할 것 같은 확률에 곱하는 감점",
}
DWTIP = {
    "DwellWeight": "글에서 잠깐이라도 멈춰 읽을 것 같은 확률",
    "ContDwellTimeWeight": "글에 머무를 것 같은 시간(연속값)에 곱하는 값",
    "ContClickDwellTimeWeight": "글을 눌러 들어간 뒤 머무를 것 같은 시간에 곱하는 값",
    "NotDwelledWeight": "멈추지 않고 그냥 스크롤로 넘길 것 같은 확률에 곱하는 작은 감점",
}
LOGTIP = {
    "add": "이 커밋에서 새로 생긴 스위치 개수예요. 대부분 OFF로 시작해요",
    "del": "이 커밋에서 없어진 스위치 개수예요",
    "on": "OFF였다가 ON으로 바뀐 스위치 개수예요. 기능이 실제로 돌기 시작했다는 뜻이에요",
    "off": "ON이었다가 OFF로 바뀐 스위치 개수예요",
    "w": "답글·좋아요 같은 행동의 가중치 숫자가 바뀐 개수예요. 노출 순위에 직접 영향을 줘요",
    "o": "후보 개수, 시간 제한, 모델 이름처럼 숫자·문자 설정값이 바뀐 개수예요",
    "f": "스위치·가중치 변화 없이 코드 파일만 바뀐 커밋이에요. 숫자는 바뀐 파일 수예요",
}


def tip(text):
    return f' tabindex="0" data-tip="{esc(text)}"'


CATS = [
    ("ranking", "랭킹·재정렬", "점수 매기기, 섞기, 다양성"),
    ("spam", "스팸·유도 라벨", "낚시·유도 감점, 신규 계정 보호"),
    ("video", "영상", "영상 캐러셀과 영상 관련 기능"),
    ("filter", "필터", "후보 글을 걸러내는 기능"),
    ("source", "후보 소스", "추천 후보를 어디서 가져올지"),
    ("exp", "실험·기록", "추적·로그·학습용 기능"),
    ("other", "기타", "그 밖의 기능"),
]


def category(n):
    if any(k in n for k in ("Ineligible", "Nsfw", "MinEngagement", "Spam", "Bait", "Toxic")):
        return "spam"
    if "Video" in n:
        return "video"
    if any(k in n for k in ("Rank", "Diversity", "Dpp", "FairShare", "Rerank", "Scor", "Blend")):
        return "ranking"
    if any(k in n for k in ("Filter", "Dedup", "Visibility", "Vf")):
        return "filter"
    if any(k in n for k in ("Source", "Retrieval", "Phoenix", "Thunder", "Simclusters", "Oon", "TweetMixer")):
        return "source"
    if any(k in n for k in ("UnderTheHood", "SideEffect", "Teacher", "Log", "Experiment", "Kafka", "Debug", "Trace", "Shadow")):
        return "exp"
    return "other"


WLABEL = {
    "ShareViaCopyLinkWeight": ("링크 복사 공유", "Copy link"),
    "ReplyWeight": ("답글", "Reply"),
    "QuoteWeight": ("인용", "Quote"),
    "ShareViaDmWeight": ("DM으로 공유", "Share via DM"),
    "FollowAuthorWeight": ("작성자 팔로우", "Follow author"),
    "ShareWeight": ("공유", "Share"),
    "RetweetWeight": ("재게시", "Repost"),
    "FavoriteWeight": ("좋아요", "Like"),
    "ClickWeight": ("게시물 클릭", "Click post"),
    "OpenLinkWeight": ("링크 열기", "Open link"),
    "PhotoExpandWeight": ("사진 펼치기", "Photo expand"),
    "QuotedClickWeight": ("인용글 클릭", "Quoted click"),
    "PostUnexploredWeight": ("미탐색 글 보너스", "Post unexplored"),
    "DwellWeight": ("머무름 여부", "Dwell"),
    "ContDwellTimeWeight": ("머문 시간 (연속값)", "Dwell time"),
    "ContClickDwellTimeWeight": ("클릭 후 머문 시간", "Click dwell time"),
    "NotDwelledWeight": ("안 머물고 넘김", "Not dwelled"),
    "ReportWeight": ("신고", "Report"),
    "MuteAuthorWeight": ("작성자 뮤트", "Mute author"),
    "NotInterestedWeight": ("관심 없음", "Not interested"),
    "BlockAuthorWeight": ("작성자 차단", "Block author"),
    "VideoOpenWeight": ("영상 열기", "Video open"),
    "VqvWeight": ("영상 시청 (VQV)", "Video quality view"),
    "QuotedVqvWeight": ("인용 영상 시청", "Quoted VQV"),
    "PostVideoWeight": ("영상 게시물", "Post video"),
    "VideoContinuationWeight": ("영상 이어보기", "Video continuation"),
    "UserVideoContinuationWeight": ("사용자 영상 이어보기", "User video continuation"),
    "ProfileClickWeight": ("프로필 클릭", "Profile click"),
    "ProfileVisitSecsWeight": ("프로필 체류 시간", "Profile visit secs"),
    "GrokAnalyzeWeight": ("그록 분석", "Grok analyze"),
    "BidirectionalFollowReplyWeightBoost": ("맞팔 답글 보너스", "Mutual reply boost"),
    "BidirectionalFollowDwellWeightBoost": ("맞팔 머문 시간 보너스", "Mutual dwell boost"),
}
DWELL = ["DwellWeight", "ContDwellTimeWeight", "ContClickDwellTimeWeight", "NotDwelledWeight"]
NEG = ["ReportWeight", "MuteAuthorWeight", "NotInterestedWeight", "BlockAuthorWeight"]


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(v):
    if v is None:
        return "?"
    s = ("%.6f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def clip(v, n=60):
    v = str(v)
    return v if len(v) <= n else v[:n] + "…"


def short(k):
    return k.split(":", 1)[1] if ":" in k else k


def sw_ko(n):
    """스위치 이름 → (한국어 이름, 설명). 번역이 없으면 None."""
    if n in KEY:
        return KEY[n]
    return KO_SW.get(n)


def name_ko(kind, n):
    if kind == "switch":
        r = sw_ko(n)
        return r[0] if r else None
    if kind == "weight":
        r = WLABEL.get(n)
        return r[0] if r else KO_W.get(n)
    return KO_ST.get(n)


def kn(kind, n):
    """업데이트 기록용: 한국어 이름 + 작은 코드 이름. 번역이 없으면 코드 이름만."""
    ko = name_ko(kind, n)
    if not ko:
        return f'<code>{esc(n)}</code>'
    return f'<span class="kn">{esc(ko)}</span> <code class="kc">{esc(n)}</code>'


MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                       "September", "October", "November", "December"], 1)}


def date_ko(t):
    m = re.fullmatch(r"\s*([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\s*", t or "")
    if m and m.group(1).capitalize() in MONTHS:
        return f"{m.group(3)}년 {MONTHS[m.group(1).capitalize()]}월 {int(m.group(2))}일"
    return t


# ---------------------------------------------------------------- history
def build_history(src, cms):
    path = os.path.join(STATE, "snapshots.json")
    cache = {}
    if os.path.exists(path):
        try:
            data = json.load(open(path))
            if data.get("schema") == SCHEMA:
                cache = data.get("snapshots", {})
        except Exception:
            cache = {}
    for c in cms:
        if c["sha"] in cache:
            continue
        hm = git(src, "show", f"{c['sha']}:{HM}")
        vm = git(src, "show", f"{c['sha']}:{VM}")
        snap = snapshot_from_texts(hm, vm)
        snap["has_hm"] = hm is not None
        stat = git(src, "show", "--format=", "--name-only", c["sha"]) or ""
        files = [f for f in stat.splitlines() if f.strip()]
        dirs = {}
        for f in files:
            d = f.split("/")[0] if "/" in f else "(루트)"
            dirs[d] = dirs.get(d, 0) + 1
        snap["files"] = len(files)
        snap["dirs"] = sorted(dirs.items(), key=lambda x: -x[1])
        cache[c["sha"]] = snap
    os.makedirs(STATE, exist_ok=True)
    json.dump({"schema": SCHEMA, "snapshots": cache}, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    return cache


def diff(prev, cur):
    d = {"sw_add": [], "sw_del": [], "sw_flip": [], "w_chg": [], "w_add": [], "w_del": [], "other_chg": []}
    if prev is None or not prev.get("has_hm"):
        return d
    ps, cs = prev["switches"], cur["switches"]
    for k in cs:
        if k not in ps:
            d["sw_add"].append((k, cs[k]))
        elif ps[k] != cs[k]:
            d["sw_flip"].append((k, ps[k], cs[k]))
    d["sw_del"] = [(k, ps[k]) for k in ps if k not in cs]
    pw, cw = prev["weights"], cur["weights"]
    for k in cw:
        if k not in pw:
            d["w_add"].append((k, cw[k]))
        elif pw[k] != cw[k]:
            d["w_chg"].append((k, pw[k], cw[k]))
    d["w_del"] = [(k, pw[k]) for k in pw if k not in cw]
    po, co = prev["other"], cur["other"]
    for k in set(po) | set(co):
        if po.get(k) != co.get(k):
            d["other_chg"].append((k, po.get(k), co.get(k)))
    d["other_chg"].sort()
    return d


def readme_updates(src):
    try:
        t = open(os.path.join(src, "README.md"), encoding="utf-8").read()
    except Exception:
        return []
    m = re.search(r"^## Notable Updates\s*$(.*?)^## ", t, re.S | re.M)
    if not m:
        return []
    out = []
    for blk in re.split(r"^### ", m.group(1), flags=re.M)[1:]:
        title, _, body = blk.partition("\n")
        items = []
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("- "):
                items.append(line[2:])
            elif line and items and not line.startswith("#") and not line.endswith(":"):
                pass
        out.append((title.strip(), items))
    return out


def md_inline(s):
    s = esc(s)
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)

    def link(m):
        url = html.unescape(m.group(2))
        if url.startswith("#"):
            return m.group(1)
        if not url.startswith("http"):
            url = f"{REPO_URL}/blob/main/{url}"
        return f'<a href="{esc(url)}" target="_blank" rel="noopener">{m.group(1)}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)


# ---------------------------------------------------------------- render
CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0b0f14;--panel:#121821;--line:#1c2a38;--txt:#e8eef4;--dim:#8b9aab;--mint:#7fdbca;--on:#3DFFA8;--blue:#1d9bf0;--red:#ff5c6c;--amber:#ffc46b}
html{background:var(--bg)}
body{color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Noto Sans CJK KR","Malgun Gothic",sans-serif;
 background-color:var(--bg);background-image:radial-gradient(900px 380px at 50% -8%,rgba(29,155,240,.12),transparent 60%),linear-gradient(rgba(255,255,255,.028) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.028) 1px,transparent 1px);
 background-size:auto,32px 32px,32px 32px;line-height:1.4;-webkit-text-size-adjust:100%;min-height:100vh}
a{color:#6ec1f5;text-decoration:none}
code,.mono{font-family:"SF Mono",Menlo,"Noto Sans Mono CJK KR",Consolas,monospace}
.wrap{max-width:1100px;margin:0 auto;padding:10px 12px 28px}
summary{list-style:none;cursor:pointer;-webkit-tap-highlight-color:transparent}
summary::-webkit-details-marker{display:none}
/* top strip */
.strip{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding:8px 12px;border:1px solid var(--line);border-radius:12px;background:linear-gradient(180deg,rgba(18,24,32,.96),rgba(12,16,22,.96))}
.pulse{width:8px;height:8px;border-radius:50%;background:var(--on);box-shadow:0 0 8px var(--on);flex:none;animation:p 2s infinite}
@keyframes p{50%{opacity:.4}}
.si{font-size:12.5px;color:#c9d4de;white-space:nowrap}
.si b{color:#f4f8fb}
.si .l{color:var(--dim);margin-right:3px}
.chips{display:flex;gap:5px;margin-left:auto}
.chip{font-size:11.5px;font-weight:800;padding:2px 7px;border-radius:7px;white-space:nowrap}
.chip.g{background:rgba(61,255,168,.12);color:var(--on);border:1px solid rgba(61,255,168,.28)}
.chip.r{background:rgba(140,154,168,.1);color:#9aa8b6;border:1px solid #2a3848}
.chip.y{background:rgba(255,184,77,.12);color:var(--amber);border:1px solid rgba(255,184,77,.3)}
.chip.a{background:rgba(29,155,240,.12);color:#6ec1f5;border:1px solid rgba(29,155,240,.28)}
.titlerow{display:flex;align-items:center;gap:8px;margin:12px 2px 8px}
h1{font-size:20px;font-weight:900;letter-spacing:-.4px;flex:1}
details.help>summary{width:28px;height:28px;border-radius:50%;border:1px solid rgba(127,219,202,.45);color:var(--mint);font-weight:900;display:grid;place-items:center;font-size:14px}
details.help[open]>summary{background:rgba(127,219,202,.15)}
.helpbox{border:1px solid rgba(127,219,202,.28);background:#0f1a1c;border-radius:12px;padding:10px 12px;margin:0 0 10px}
.helpbox ol{padding-left:18px;display:grid;gap:4px;font-size:13px;color:#cfd9e2}
.helpbox b{color:#fff}
/* tabs */
.tabs{position:sticky;top:0;z-index:5;display:grid;grid-template-columns:repeat(3,1fr);gap:4px;padding:4px;margin-bottom:10px;border:1px solid var(--line);border-radius:12px;background:rgba(12,16,22,.96);backdrop-filter:blur(6px)}
.tabs a{text-align:center;padding:9px 4px;border-radius:9px;color:#9fb0c0;font-weight:800;font-size:14px}
.tabs a.act{background:#16324a;color:#fff;box-shadow:inset 0 0 0 1px rgba(29,155,240,.5)}
.tab{display:none}.tab.act{display:block}
.js-off .tab{display:block}
.note{font-size:11.5px;color:var(--dim);margin:0 2px 8px}
/* groups */
details.grp{border:1px solid var(--line);border-radius:12px;background:linear-gradient(180deg,rgba(18,24,33,.94),rgba(14,18,25,.94));margin-bottom:8px}
details.grp>summary{display:flex;align-items:center;gap:8px;padding:10px 12px}
details.grp>summary h3{font-size:15px;font-weight:800;flex:1}
details.grp>summary .arr{color:var(--mint);font-size:12px;transition:transform .15s}
details.grp[open]>summary .arr{transform:rotate(90deg)}
.cnt{font-size:11.5px;color:var(--dim);font-weight:700;white-space:nowrap}
.cnt .o{color:var(--on)}
.gb{padding:0 10px 10px}
.tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
@media(min-width:700px){.tiles{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:980px){.tiles{grid-template-columns:repeat(4,minmax(0,1fr))}}
details.tile{border:1px solid #1f2c3a;border-radius:10px;background:#0f151d;min-width:0}
details.tile.on{border-color:rgba(61,255,168,.35);background:linear-gradient(180deg,rgba(11,61,44,.45),rgba(11,40,30,.25))}
details.tile.hov>summary{cursor:help}
details.tile>summary{display:grid;grid-template-columns:9px minmax(0,1fr);gap:7px;align-items:center;padding:7px 8px}
.led{width:8px;height:8px;border-radius:50%;background:#2a333d;box-shadow:inset 0 0 0 1px #3a4652}
.on .led{background:var(--on);box-shadow:0 0 6px var(--on),0 0 12px rgba(61,255,168,.5)}
.tn{font-size:13px;font-weight:800;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ts{display:flex;gap:4px;align-items:center;margin-top:2px;font-size:10.5px;font-weight:800;color:#6b7682;letter-spacing:.04em}
.on .ts .st{color:var(--on)}
.badge{font-size:9.5px;font-weight:800;padding:0 4px;border-radius:4px;background:rgba(255,184,77,.14);color:var(--amber);border:1px solid rgba(255,184,77,.35);letter-spacing:0}
.badge.chg{background:rgba(255,92,108,.14);color:#ff8f9a;border-color:rgba(255,92,108,.4)}
.badge.vm{background:#151c25;color:#7f91a3;border-color:#2a3848}
.tx{padding:0 9px 8px 24px;font-size:12px;color:#b7c3ce}
.tx code{display:block;font-size:10.5px;color:#8aa0b3;overflow-wrap:anywhere;margin-bottom:2px}
details.rest{margin-top:8px}
details.rest>summary{font-size:12px;color:var(--dim);font-weight:700;padding:4px 2px}
details.rest>summary:before,details.more>summary:before{content:"▸ ";color:var(--mint)}
details.rest[open]>summary:before,details.more[open]>summary:before{content:"▾ "}
.dense{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:2px 8px;padding-top:4px}
.dn{display:flex;align-items:center;gap:6px;font-family:"SF Mono",Menlo,monospace;font-size:11px;color:#8fa0b0;min-width:0}
.dn span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dn.on{color:#d9fbe9}
.dn .led{width:6px;height:6px;flex:none}
.dn.tip{text-decoration:none}
.dn .dk{flex:none;max-width:62%;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Noto Sans CJK KR",sans-serif;font-size:12px;font-weight:700;color:#b9c6d2}
.dn.on .dk{color:#e6fff1}
.dn .dc{flex:1;min-width:0;font-size:9.5px;color:#5f7080}
.dn .dc.en{font-size:11px;color:inherit}
.dn.on .dc{color:#6fa88c}
/* weights */
.card{border:1px solid var(--line);border-radius:12px;background:linear-gradient(180deg,rgba(18,24,33,.94),rgba(14,18,25,.94));padding:10px 12px;margin-bottom:8px}
.ch3{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.ch3 h3{font-size:15px;font-weight:800;flex:1}
.wrow{display:grid;grid-template-columns:96px minmax(0,1fr) 46px;gap:8px;align-items:center;height:25px}
@media(min-width:700px){.wrow{grid-template-columns:150px minmax(0,1fr) 56px}}
.wl{font-size:12.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.track{height:10px;background:#18212c;border-radius:5px;overflow:hidden;box-shadow:inset 0 0 0 1px #223040}
.bar{height:100%;border-radius:5px;background:linear-gradient(90deg,#1572b8,#1d9bf0);box-shadow:0 0 8px rgba(29,155,240,.45)}
.bar.hi{background:linear-gradient(90deg,#16a37a,#3DFFA8)}
.wv{text-align:right;font-size:13.5px;font-weight:900;font-variant-numeric:tabular-nums}
.wv i{display:block;font-style:normal;font-size:9px;color:var(--amber);font-weight:800;line-height:1}
.mini{font-size:11.5px;color:var(--dim)}
.mini b{color:#e8eef4}
.negs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.nb{border:1px solid rgba(255,92,108,.5);background:rgba(255,92,108,.07);border-radius:10px;padding:6px 7px;text-align:center}
.nv{font-size:17px;font-weight:900;color:var(--red);font-variant-numeric:tabular-nums}
.nk{font-size:11.5px;font-weight:700;color:#e3c9cc}
details.more{border:1px solid var(--line);border-radius:12px;background:rgba(18,24,33,.9);margin-bottom:8px}
details.more>summary{padding:10px 12px;font-size:13.5px;font-weight:800}
details.more>summary .cnt{margin-left:6px}
.mb{padding:0 12px 10px}
.zeros{display:flex;flex-wrap:wrap;gap:4px}
.zero{font-size:11.5px;padding:2px 7px;border-radius:7px;background:#151c25;border:1px solid #2a3848;color:#cfd9e2}
table.cmp{width:100%;border-collapse:collapse;font-size:12px}
table.cmp td,table.cmp th{padding:4px 4px;border-bottom:1px solid #1c2a38;text-align:left}
table.cmp th{color:var(--dim);font-weight:700}
table.cmp .n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.cmp tr.diff td{color:var(--amber)}
/* log */
details.ev{border:1px solid var(--line);border-radius:10px;background:rgba(18,24,33,.92);margin-bottom:5px}
details.ev>summary{display:flex;align-items:center;gap:6px;padding:7px 10px;flex-wrap:wrap}
.ed{font-size:13.5px;font-weight:900;min-width:48px}
.et{font-size:11px;color:var(--dim);min-width:34px}
.esha{font-family:monospace;font-size:11px;color:#6ec1f5}
.echips{display:flex;flex-wrap:wrap;gap:3px;margin-left:auto}
.c{font-size:10.5px;font-weight:800;padding:1px 5px;border-radius:5px;white-space:nowrap}
.c.add{background:rgba(61,255,168,.12);color:var(--on)}
.c.del{background:rgba(255,92,108,.12);color:#ff8f9a}
.c.flip{background:rgba(29,155,240,.14);color:#6ec1f5}
.c.w{background:rgba(255,184,77,.14);color:var(--amber)}
.c.o{background:#1a222c;color:#8b9aab}
.eb{padding:0 10px 8px;display:grid;gap:2px;font-size:12px;color:#cfd9e2;overflow-wrap:anywhere}
.eb code{font-size:11px;color:#e2ebf3}
.eb .f{color:var(--dim);font-size:11px;margin-top:2px}
.eb .kn{font-weight:700;color:#f1f6fa}
.eb code.kc{font-size:10px;color:#6f8294}
.eb .os{display:inline}
.nu .en{font-size:11px;color:#7d8d9c;margin-top:2px}
.nu details.orig>summary{display:inline-block;font-size:11px;color:var(--mint);font-weight:700;margin-top:2px}
.nu details.orig>summary:before{content:"▸ "}
.nu details.orig[open]>summary:before{content:"▾ "}
.eb a{font-size:11px}
.nu{padding:6px 0;border-top:1px solid var(--line)}
.nu h4{font-size:13px;color:var(--mint);margin-bottom:3px}
.nu ul{padding-left:16px;font-size:12.5px;color:#cfd9e2;display:grid;gap:3px;overflow-wrap:anywhere}
.nu code{font-size:11px}
.tip{cursor:help;text-decoration:underline dotted rgba(127,219,202,.55);text-underline-offset:3px;text-decoration-thickness:1px;outline:none}
.tip:focus-visible{box-shadow:0 0 0 2px rgba(127,219,202,.6);border-radius:4px}
.chip.tip,.c.tip,.badge.tip,.nb.tip{text-decoration:none;border-style:dashed}
.c.tip{box-shadow:inset 0 -1px 0 rgba(255,255,255,.18)}
.nb.tip{border-style:solid}
.i.tip{text-decoration:none;font-size:.78em;color:var(--mint);opacity:.75;margin-left:4px;font-weight:700;vertical-align:1px;padding:2px}
.tabs a.act .i{opacity:1}
#tt{position:fixed;z-index:50;max-width:min(280px,calc(100vw - 20px));padding:8px 11px;border-radius:10px;background:#16212c;color:#e8eef4;font-size:12.5px;line-height:1.45;font-weight:500;
 border:1px solid rgba(127,219,202,.45);box-shadow:0 8px 24px rgba(0,0,0,.55),0 0 14px rgba(127,219,202,.12);pointer-events:none;opacity:0;transform:translateY(3px);transition:opacity .12s,transform .12s;left:0;top:0}
#tt.show{opacity:1;transform:none}
#tt:after{content:"";position:absolute;left:var(--ax,50%);width:9px;height:9px;background:#16212c;transform:translateX(-50%) rotate(45deg)}
#tt.up:after{bottom:-5px;border-right:1px solid rgba(127,219,202,.45);border-bottom:1px solid rgba(127,219,202,.45)}
#tt.down:after{top:-5px;border-left:1px solid rgba(127,219,202,.45);border-top:1px solid rgba(127,219,202,.45)}
footer{margin-top:14px;font-size:11px;color:var(--dim);line-height:1.5}
footer .w{color:#ff8f73}
"""

SHORT_MEAN_WIDTH = 0


def render(ctx):
    latest, snap, first_seen, prev_run = ctx["latest"], ctx["snap"], ctx["first_seen"], ctx["prev_run"]
    now = ctx["now"]
    sw = snap["switches"]
    on_all = sum(sw.values())
    hm_b = {k: v for k, v in sw.items() if k.startswith("home-mixer:")}
    vm_b = {k: v for k, v in sw.items() if k.startswith("vm-ranker:")}
    hm_on, vm_on = sum(hm_b.values()), sum(vm_b.values())
    cutoff = now - dt.timedelta(days=NEW_DAYS)
    prev_sw = (prev_run or {}).get("switches", {})
    prev_w = (prev_run or {}).get("weights", {})

    def is_new(k):
        fs = first_seen.get(k)
        return bool(fs) and kst(fs) >= cutoff and not ctx["first_is_base"].get(k)

    def md(d):
        return f"{d.month}/{d.day}"

    new_count = sum(1 for k in sw if is_new(k))
    lt = kst(latest["date"])
    out = []
    A = out.append
    A('<!doctype html><html lang="ko" class="js-off"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
      '<meta name="theme-color" content="#0b0f14"><title>엑스 알고리즘 대시보드</title>'
      f'<style>{CSS}</style></head><body><div class="wrap">')
    A('<div class="strip"><span class="pulse"></span>'
      f'<span class="si tip"{tip("X가 공개 저장소에 마지막으로 올린 코드 버전이에요. 커밋은 코드 수정 묶음 하나이고, 숫자·영문은 그 버전의 이름표예요. 날짜는 한국 시간")}><span class="l">최신 커밋</span><a href="{REPO_URL}/commit/{latest["sha"]}" target="_blank" rel="noopener"><b>{latest["sha"][:7]}</b></a> · <b>{lt:%m.%d %H:%M}</b></span>'
      f'<span class="si tip"{tip("이 사이트가 저장소를 마지막으로 읽어서 새로 그린 시간이에요. 매일 오전 6시(한국 시간)에 자동으로 갱신돼요")}><span class="l">갱신</span><b>{now:%m.%d %H:%M}</b> (한국 시간)</span>'
      f'<span class="chips"><span class="chip g tip"{tip(f"ON {on_all} = 전체 스위치 {len(sw)}개 중 켜진 개수예요. 많이 켜져 있어도 점수가 더 붙는 건 아니에요")}>ON {on_all}</span>'
      f'<span class="chip r tip"{tip(f"OFF {len(sw) - on_all} = 코드에는 있지만 기본값으로는 꺼진 기능 개수예요. 나중에 켜지면 변화가 생겨요")}>OFF {len(sw) - on_all}</span>'
      f'<span class="chip y tip"{tip(f"NEW {new_count} = 최근 {NEW_DAYS}일 안에 새로 생긴 스위치 개수예요")}>NEW {new_count}</span></span></div>')
    A('<div class="titlerow"><h1>엑스 알고리즘 대시보드</h1>'
      '<details class="help" id="help"><summary aria-label="패널 읽는 법">?</summary></details></div>'
      '<div class="helpbox" id="helpbox" hidden><ol>'
      '<li><b>ON/OFF는 기능이 돌고 있는지만</b> 알려줘요. 켜졌다고 점수를 더 주는 게 아니에요</li>'
      '<li>이름에 <b>Filter</b>가 붙으면 걸러내고, <b>Diversity·FairShare</b>면 섞고, <b>Ineligible·Exclude</b>면 점수를 빼요</li>'
      '<li><b>가중치</b>는 각 행동을 "얼마나 쳐줄까", <b>스위치</b>는 그 기능을 "쓸까 말까"예요</li>'
      f'<li><b>NEW</b>는 최근 {NEW_DAYS}일 안에 새로 생긴 스위치예요</li>'
      '<li>모두 <b>공개 코드 기본값</b>이라 실제 서비스와 같은지는 확인할 수 없어요</li></ol>'
      '<div class="mini" style="margin-top:6px">매일 오전 6시(한국 시간) 자동 갱신 · 출처 '
      f'<a href="{REPO_URL}" target="_blank" rel="noopener">xai-org/x-algorithm</a></div></div>')
    A('<nav class="tabs">'
      f'<a href="#switch" data-t="switch">스위치<span class="i tip"{tip("기능별 ON/OFF 상태예요. 켜짐은 그 기능이 돌고 있다는 뜻이지, 점수를 더 준다는 뜻이 아니에요")}>ⓘ</span></a>'
      f'<a href="#weight" data-t="weight">가중치<span class="i tip"{tip("답글·좋아요·공유 같은 행동을 얼마나 쳐주는지 숫자로 보여줘요. 클수록 그런 반응이 나올 글을 위로 올려요")}>ⓘ</span></a>'
      f'<a href="#log" data-t="log">업데이트 기록<span class="i tip"{tip("X가 코드를 올린 날짜별로 스위치·가중치·설정이 어떻게 바뀌었는지 정리했어요")}>ⓘ</span></a></nav>')

    # ---------------- switch tab
    A(f'<section class="tab" id="t-switch"><div class="note">home-mixer {len(hm_b)}개 (ON {hm_on}) · vm-ranker {len(vm_b)}개 (ON {vm_on}) · 핵심과 NEW만 표시 · 칸을 누르면 설명</div>')
    groups = {c[0]: [] for c in CATS}
    for k, v in sw.items():
        groups[category(short(k))].append((k, v))
    first = True
    for cid, title, desc in CATS:
        items = groups[cid]
        if not items:
            continue
        items.sort(key=lambda kv: (not is_new(kv[0]), short(kv[0]) not in KEY, not kv[1], short(kv[0])))
        key_items = [kv for kv in items if short(kv[0]) in KEY or is_new(kv[0]) or (kv[0] in prev_sw and prev_sw[kv[0]] != kv[1])]
        rest = [kv for kv in items if kv not in key_items]
        on = sum(v for _, v in items)
        nn = sum(1 for k, _ in items if is_new(k))
        A(f'<details class="grp"{" open" if first else ""}><summary><span class="arr">▶</span><h3>{title}<span class="i tip"{tip(CAT_TIP[cid])}>ⓘ</span></h3>'
          f'<span class="cnt"><span class="o tip"{tip(f"ON {on} = 이 그룹 스위치 {len(items)}개 중 켜진 개수예요. 많이 켜져도 점수가 더 붙는 건 아니에요")}>ON {on}</span> · '
          f'<span class="tip"{tip(f"OFF {len(items) - on} = 이 그룹에서 꺼진 개수예요. 코드엔 있지만 지금 기본값으로는 안 돌아가요")}>OFF {len(items) - on}</span></span>'
          + (f'<span class="badge tip"{tip(f"NEW {nn} = 이 그룹에서 최근 {NEW_DAYS}일 안에 새로 생긴 스위치 개수예요")}>NEW {nn}</span>' if nn else "") + '</summary><div class="gb"><div class="tiles">')
        first = False
        for k, v in key_items:
            n = short(k)
            ko, mean = sw_ko(n) or (n, "")
            badges = ""
            if is_new(k):
                badges += f'<span class="badge">NEW {md(kst(first_seen[k]))}</span>'
            if k in prev_sw and prev_sw[k] != v:
                badges += f'<span class="badge chg">{"켜짐" if v else "꺼짐"}</span>'
            if k.startswith("vm-ranker:"):
                badges += '<span class="badge vm">vm</span>'
            A(f'<details class="tile hov{" on" if v else ""}" data-tip="{esc(ko + " · " + (mean or n))}"><summary><span class="led"></span><div style="min-width:0">'
              f'<div class="tn">{esc(ko)}</div><div class="ts"><span class="st">{"ON" if v else "OFF"}</span>{badges}</div></div></summary>'
              f'<div class="tx"><code>{esc(n)}</code>{esc(mean) if mean else "설명 준비 중"}</div></details>')
        A('</div>')
        if rest:
            ron = sum(v for _, v in rest)
            A(f'<details class="rest"><summary>나머지 {len(rest)}개 (ON {ron} · OFF {len(rest) - ron})</summary><div class="dense">')
            for k, v in rest:
                n = short(k)
                vmt = " · vm" if k.startswith("vm-") else ""
                r = sw_ko(n)
                if r:
                    t = r[0] + (" · " + r[1] if r[1] else "") + " (" + n + vmt + ")"
                    A(f'<div class="dn tip{" on" if v else ""}"{tip(t)}><span class="led"></span><span class="dk">{esc(r[0])}</span><span class="dc">{esc(n)}{vmt}</span></div>')
                else:
                    A(f'<div class="dn{" on" if v else ""}"><span class="led"></span><span class="dc en" title="{esc(n)}">{esc(n)}{vmt}</span></div>')
            A('</div></details>')
        A('</div></details>')
    A('</section>')

    # ---------------- weight tab
    W = {short(k): v for k, v in snap["weights"].items() if k.startswith("home-mixer:")}
    WV = {short(k): v for k, v in snap["weights"].items() if k.startswith("vm-ranker:")}
    last_chg = ctx["last_weight_change"]

    def chg(n):
        k = "home-mixer:" + n
        if k in prev_w and prev_w[k] != W.get(n):
            return f'<i title="지난 갱신 {fmt(prev_w[k])}">방금 {fmt(prev_w[k])}→</i>'
        if k in last_chg and kst(last_chg[k][0]) >= now - dt.timedelta(days=30):
            d, o, nv = last_chg[k]
            return f'<i title="{fmt(o)} → {fmt(nv)}">{md(kst(d))} 변경</i>'
        return ""

    A('<section class="tab" id="t-weight"><div class="note">home-mixer 기본값 · 실제 횟수가 아니라 그 행동이 나올 <b>예측 확률</b>에 곱해요</div>')
    pos = [(n, v) for n, v in W.items() if v is not None and v > 0 and n not in DWELL and n not in NEG
           and not n.startswith("VideoCarousel") and "Boost" not in n]
    boost = W.get("BidirectionalFollowReplyWeightBoost")
    if boost and W.get("ReplyWeight") is not None:
        pos.append(("__mutual", W["ReplyWeight"] + boost))
    pos.sort(key=lambda x: -x[1])
    mx = max([v for _, v in pos] or [1])
    A('<div class="card"><div class="ch3"><h3>➕ 플러스 신호</h3><span class="mini">클수록 위로</span></div>')
    for n, v in pos:
        if n == "__mutual":
            ko, c = f'맞팔 답글 ({fmt(W["ReplyWeight"])}+{fmt(boost)})', chg("BidirectionalFollowReplyWeightBoost")
            n_tip = WTIP["__mutual"]
        else:
            ko, c = WLABEL.get(n, (n,))[0], chg(n)
            n_tip = WTIP.get(n, f"{n} 가중치")
        w = max(v / mx * 100, 1.5)
        A(f'<div class="wrow"><div class="wl"><span class="tip"{tip(n_tip)}>{esc(ko)}</span></div><div class="track"><div class="bar{" hi" if v >= mx * .99 else ""}" style="width:{w:.1f}%"></div></div><div class="wv">{fmt(v)}{c}</div></div>')
    dw = " · ".join(f'<span class="tip"{tip(DWTIP[n])}>{WLABEL[n][0]}</span> <b>{fmt(W[n])}</b>' for n in DWELL if n in W)
    A(f'<div class="mini" style="margin-top:6px"><span class="tip"{tip("글에 얼마나 머무를지 예측한 값에 곱하는 가중치예요. 값의 단위(초·밀리초 등)는 코드에서 확인 못 했어요")}>머무는 시간</span> · {dw}</div></div>')
    A('<div class="card"><div class="ch3"><h3>➖ 마이너스 신호</h3><span class="mini">신고 1번 = 좋아요 수백 번이 아니에요</span></div><div class="negs">')
    for n in NEG:
        if n in W:
            A(f'<div class="nb tip"{tip(NEGTIP[n])}><div class="nv">{fmt(W[n])}</div><div class="nk">{WLABEL[n][0]}</div>{("<div class=mini>" + chg(n) + "</div>") if chg(n) else ""}</div>')
    A('</div></div>')
    zeros = [n for n, v in W.items() if v == 0 and not n.startswith("VideoCarousel")]
    vc = [(n, v) for n, v in W.items() if n.startswith("VideoCarousel")]
    A(f'<details class="more"><summary>0점 항목<span class="cnt">{len(zeros)}개 · 홈 피드 영상 가중치 전부 0</span></summary><div class="mb"><div class="zeros">')
    for n in zeros:
        A(f'<span class="zero" title="{esc(n)}">{esc(WLABEL.get(n, (n,))[0])}</span>')
    A('</div>')
    if vc:
        A('<div class="mini" style="margin:8px 0 2px">영상 캐러셀 전용 (홈 피드와 다른 영역)</div><table class="cmp">')
        for n, v in vc:
            A(f'<tr><td class="mono">{esc(n.replace("VideoCarousel", ""))}</td><td class="n">{fmt(v)}</td></tr>')
        A('</table>')
    A('</div></details>')
    common = sorted(set(W) & set(WV))
    ndiff = sum(1 for n in common if W[n] != WV[n])
    A(f'<details class="more"><summary>vm-ranker 기본값 비교<span class="cnt">{ndiff}개 다름</span></summary><div class="mb"><table class="cmp"><tr><th>항목</th><th class="n">home-mixer</th><th class="n">vm-ranker</th></tr>')
    for n in sorted(common, key=lambda n: W[n] == WV[n]):
        A(f'<tr{" class=diff" if W[n] != WV[n] else ""}><td>{esc(WLABEL.get(n, (n,))[0])}</td><td class="n">{fmt(W[n])}</td><td class="n">{fmt(WV[n])}</td></tr>')
    A('</table></div></details></section>')

    # ---------------- log tab
    tl = ctx["timeline"]
    A(f'<section class="tab" id="t-log"><div class="note">커밋 {len(tl)}개 · 한국 시간 · 줄을 누르면 자세히</div>')

    def ev(c, d, s):
        t = kst(c["date"])
        chips = []
        if d["sw_add"]:
            chips.append(f'<span class="c add tip"{tip(LOGTIP["add"])}>스위치 +{len(d["sw_add"])}</span>')
        if d["sw_del"]:
            chips.append(f'<span class="c del tip"{tip(LOGTIP["del"])}>스위치 −{len(d["sw_del"])}</span>')
        on_n = sum(1 for _, _, b in d["sw_flip"] if b)
        off_n = len(d["sw_flip"]) - on_n
        if on_n:
            chips.append(f'<span class="c flip tip"{tip(LOGTIP["on"])}>켜짐 {on_n}</span>')
        if off_n:
            chips.append(f'<span class="c flip tip"{tip(LOGTIP["off"])}>꺼짐 {off_n}</span>')
        if d["w_chg"] or d["w_add"] or d["w_del"]:
            chips.append(f'<span class="c w tip"{tip(LOGTIP["w"])}>가중치 {len(d["w_chg"]) + len(d["w_add"]) + len(d["w_del"])}</span>')
        if d["other_chg"]:
            chips.append(f'<span class="c o tip"{tip(LOGTIP["o"])}>설정 {len(d["other_chg"])}</span>')
        if not chips:
            chips.append(f'<span class="c o tip"{tip(LOGTIP["f"])}>파일 {s.get("files", 0)}</span>')
        lines = []
        for k, v in d["sw_add"]:
            lines.append(f'<div><span class="c add">추가</span> {kn("switch", short(k))} {"ON" if v else "OFF"}</div>')
        for k, v in d["sw_del"]:
            lines.append(f'<div><span class="c del">삭제</span> {kn("switch", short(k))}</div>')
        for k, a, b2 in d["sw_flip"]:
            lines.append(f'<div><span class="c flip">{"켜짐" if b2 else "꺼짐"}</span> {kn("switch", short(k))}</div>')
        for k, a, b2 in d["w_chg"]:
            lines.append(f'<div><span class="c w">가중치</span> {kn("weight", short(k)) if short(k) not in WLABEL else esc(WLABEL[short(k)][0])} <b>{fmt(a)} → {fmt(b2)}</b>{" · vm" if k.startswith("vm-") else ""}</div>')
        for k, v in d["w_add"]:
            lines.append(f'<div><span class="c w">가중치 추가</span> {kn("weight", short(k))} = {fmt(v)}</div>')
        for k, v in d["w_del"]:
            lines.append(f'<div><span class="c del">가중치 삭제</span> {kn("weight", short(k))}</div>')
        oc = d["other_chg"]
        if oc:
            ex = ", ".join(kn("setting", short(k)) for k, _, _ in oc[:8]) + (f" 외 {len(oc) - 8}개" if len(oc) > 8 else "")
            lines.append(f'<div><span class="c o">설정</span> {ex}</div>')
        dirs = ", ".join(f"{esc(n)} {c2}" for n, c2 in s.get("dirs", [])[:5])
        lines.append(f'<div class="f">바뀐 파일 {s.get("files", 0)}개 · {dirs}</div>')
        lines.append(f'<a href="{REPO_URL}/commit/{c["sha"]}" target="_blank" rel="noopener">GitHub에서 커밋 보기 ↗</a>')
        return (f'<details class="ev"><summary><span class="ed">{t.month}/{t.day}</span><span class="et">{t:%H:%M}</span>'
                f'<span class="esha">{c["sha"][:7]}</span><span class="echips">{"".join(chips)}</span></summary>'
                f'<div class="eb">{"".join(lines)}</div></details>')

    for c, d, s in tl[:7]:
        A(ev(c, d, s))
    if len(tl) > 7:
        A(f'<details class="more" style="margin-top:6px"><summary>더 보기<span class="cnt">이전 커밋 {len(tl) - 7}개</span></summary><div class="mb">')
        for c, d, s in tl[7:]:
            A(ev(c, d, s))
        A('</div></details>')
    nt = ctx["notable"]
    n_all = sum(len(items) for _, items in nt)
    n_ko = sum(1 for _, items in nt for x in items if KO_NOTE.get(x))
    lab = "한국어 번역" if n_ko == n_all else ("영어 원문" if n_ko == 0 else f"번역 {n_ko}/{n_all}")
    A(f'<details class="more"><summary>README 공식 공지<span class="cnt">{len(nt)}건 · {lab}'
      + (f' · 최근 {esc(date_ko(nt[0][0]))}' if nt else "") + '</span></summary><div class="mb">')

    def note_li(x):
        ko = KO_NOTE.get(x)
        if not ko:
            return f'<li>{md_inline(x)}<div class="en">아직 번역 전이라 영어 원문이에요</div></li>'
        return (f'<li>{md_inline(ko)}<details class="orig"><summary>원문 보기</summary>'
                f'<div class="en">{md_inline(x)}</div></details></li>')
    for title, items in nt:
        A(f'<div class="nu"><h4>{esc(date_ko(title))}</h4><ul>' + "".join(note_li(x) for x in items) + '</ul></div>')
    A('</div></details></section>')
    A(f'<footer>공개 코드 기본값 · <span class="w">실제 서비스 적용 여부는 확인할 수 없어요 · 추천 순위용 점수이고 수익 지급액과는 별개예요</span><br>'
      f'최신 커밋 {latest["sha"][:7]} ({lt:%Y-%m-%d %H:%M} 한국 시간) · 마지막 갱신 {now:%Y-%m-%d %H:%M} 한국 시간</footer>')
    A("""</div><script>
(function(){var h=document.documentElement;h.classList.remove('js-off');
var tabs=['switch','weight','log'];
function show(){var t=(location.hash||'').slice(1);if(tabs.indexOf(t)<0)t='switch';
tabs.forEach(function(x){document.getElementById('t-'+x).classList.toggle('act',x===t);
document.querySelector('.tabs a[data-t="'+x+'"]').classList.toggle('act',x===t);});}
document.querySelectorAll('.tabs a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();
history.replaceState(null,'','#'+a.dataset.t);show();window.scrollTo(0,0);});});
window.addEventListener('hashchange',show);show();
var hp=document.getElementById('help'),hb=document.getElementById('helpbox');
hp.addEventListener('toggle',function(){hb.hidden=!hp.open;});
var tt=document.createElement('div');tt.id='tt';tt.setAttribute('role','tooltip');document.body.appendChild(tt);var cur=null;
function place(el){var r=el.getBoundingClientRect();tt.classList.remove('up','down');var w=tt.offsetWidth,h=tt.offsetHeight,vw=document.documentElement.clientWidth;
var x=Math.min(Math.max(8,r.left+r.width/2-w/2),vw-w-8),up=r.top>h+12;var y=up?r.top-h-9:r.bottom+9;
tt.style.left=x+'px';tt.style.top=y+'px';tt.style.setProperty('--ax',Math.min(Math.max(10,r.left+r.width/2-x),w-10)+'px');tt.classList.add(up?'up':'down');}
function open(el){cur=el;tt.textContent=el.getAttribute('data-tip');el.setAttribute('aria-describedby','tt');tt.classList.add('show');place(el);}
function close(){if(cur)cur.removeAttribute('aria-describedby');cur=null;tt.classList.remove('show');}
var touch=window.matchMedia('(hover: none)').matches;
document.querySelectorAll('.tip').forEach(function(el){
if(!touch){el.addEventListener('mouseenter',function(){open(el);});el.addEventListener('mouseleave',close);}
el.addEventListener('focus',function(){if(!touch)open(el);});el.addEventListener('blur',function(){if(!touch)close();});
el.addEventListener('click',function(e){if(e.target.closest('a')&&e.target.closest('a')!==el&&!e.target.classList.contains('i'))return;
e.preventDefault();e.stopPropagation();if(cur===el&&touch){close();}else{open(el);}});
el.addEventListener('keydown',function(e){if(e.key==='Escape'){close();el.blur();}});});
document.addEventListener('click',function(e){if(cur&&!e.target.closest('.tip'))close();});
if(!touch)document.querySelectorAll('.hov').forEach(function(el){var sm=el.querySelector('summary');sm.addEventListener('mouseenter',function(){if(!el.open)open(el);});sm.addEventListener('mouseleave',close);el.addEventListener('toggle',function(){if(el.open&&cur===el)close();});});
window.addEventListener('scroll',function(){if(cur)place(cur);},{passive:true});
document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});})();
</script></body></html>""")
    return "".join(out)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, ".src"))
    ap.add_argument("--days", type=int, default=0, help="타임라인 기간 (0이면 전체)")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    if not a.no_fetch:
        ensure_source(a.src)
    cms = commits(a.src)
    snaps = build_history(a.src, cms)
    latest = cms[0]
    snap = snaps[latest["sha"]]
    chrono = list(reversed(cms))
    first_seen, first_is_base, last_weight_change = {}, {}, {}
    base_done = False
    prev = None
    tl = []
    for c in chrono:
        s = snaps[c["sha"]]
        if s.get("has_hm"):
            for k in s["switches"]:
                if k not in first_seen:
                    first_seen[k] = c["date"]
                    first_is_base[k] = not base_done
            base_done = True
        d = diff(prev, s)
        for k, o, n in d["w_chg"]:
            last_weight_change[k] = (c["date"], o, n)
        tl.append((c, d, s))
        if s.get("has_hm"):
            prev = s
    now = dt.datetime.now(KST)
    if a.days:
        lim = now - dt.timedelta(days=a.days)
        tl = [x for x in tl if kst(x[0]["date"]) >= lim]
    tl.reverse()
    lr_path = os.path.join(STATE, "last_run.json")
    prev_run = None
    if os.path.exists(lr_path):
        try:
            prev_run = json.load(open(lr_path))
        except Exception:
            prev_run = None
    # 같은 커밋이면 지난 실행의 비교 기준을 유지 (하루에 여러 번 돌아도 변화 표시가 사라지지 않게)
    if prev_run and prev_run.get("sha") == latest["sha"] and prev_run.get("base"):
        base = prev_run["base"]
    else:
        base = {"switches": prev_run["switches"], "weights": prev_run["weights"], "sha": prev_run.get("sha")} if prev_run else None
    ctx = {"latest": latest, "snap": snap, "first_seen": first_seen, "first_is_base": first_is_base, "prev_run": base,
           "now": now, "timeline": tl, "notable": readme_updates(a.src), "last_weight_change": last_weight_change}
    os.makedirs(SITE, exist_ok=True)
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(render(ctx))
    open(os.path.join(SITE, ".nojekyll"), "w").write("")
    json.dump({"sha": latest["sha"], "refreshed": now.isoformat(), "switches": snap["switches"], "weights": snap["weights"], "base": base},
              open(lr_path, "w"), ensure_ascii=False, indent=1, sort_keys=True)
    hm = {k: v for k, v in snap["switches"].items() if k.startswith("home-mixer:")}
    print(f"latest {latest['sha'][:7]} {kst(latest['date']):%Y-%m-%d %H:%M KST} | param! hm={snap['hm_macros']} vm={snap['vm_macros']} | "
          f"hm bools={len(hm)} on={sum(hm.values())} off={len(hm) - sum(hm.values())} | commits={len(cms)}")


if __name__ == "__main__":
    main()
