"""'노출 제한' 탭. 소스에서 매번 읽어 만든다. 손으로 쓴 건 한국어 설명뿐(ko_limits.json)."""
import html, json, os, re
import limits_parse as P

HERE = os.path.dirname(os.path.abspath(__file__))


def esc(s):
    return html.escape(str(s), quote=True)


def tip(t):
    return f' tabindex="0" data-tip="{esc(t)}"'


def load_ko():
    try:
        with open(os.path.join(HERE, "ko_limits.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def days(ms):
    if not ms:
        return None
    d = ms / 86400000
    return f"{d:g}일" if d >= 1 else f"{ms / 3600000:g}시간"


def secs_ko(s):
    try:
        s = int(float(s))
    except (TypeError, ValueError):
        return str(s)
    if s and s % 86400 == 0:
        return f"{s // 86400}일"
    if s and s % 3600 == 0:
        return f"{s // 3600}시간"
    if s and s % 60 == 0:
        return f"{s // 60}분"
    return f"{s}초"


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:.6f}".rstrip("0").rstrip(".") if abs(f) < 0.001 and f else f"{f:g}"


def code(s):
    return f'<code>{esc(s)}</code>'


def src_line(*files):
    return '<div class="srcl"><span class="bl">출처</span>' + " · ".join(code(f) for f in files if f) + '</div>'


CSS = """
/* limits tab */
.lim .sum{padding-left:17px;display:grid;gap:3px;font-size:13px;color:#dbe4ec}.lim .sum b{color:#fff}
.lg{display:grid;gap:7px}
@media(min-width:900px){.lg{grid-template-columns:repeat(2,minmax(0,1fr));align-items:start}}
.lc{border:1px solid var(--line);border-radius:12px;background:linear-gradient(180deg,rgba(18,24,33,.94),rgba(14,18,25,.94));padding:9px 12px;scroll-margin-top:70px}
.lc:target{box-shadow:0 0 0 2px rgba(29,155,240,.7)}
.lh{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin-bottom:5px}
.lh h4{font-size:14px;font-weight:800;margin-right:2px}
.lk{font-size:10px;color:#8fb3cf;background:#101820;border:1px solid #22344a;border-radius:5px;padding:0 5px;overflow-wrap:anywhere}
.lt{font-size:10px;font-weight:800;border-radius:5px;padding:0 5px;background:#1a2430;color:#9fb0c0}
.sv{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;margin:4px 0 6px}
.sv div{border:1px solid #213040;border-radius:8px;padding:4px 6px;background:#0f151d;min-width:0}
.sv .sl{display:block;font-size:10px;color:var(--dim);font-weight:700}
.sv b{font-size:12px}.sv .hide b{color:var(--red)}.sv .blur b{color:var(--amber)}.sv .none b{color:#6f8294;font-weight:700}
.lx{font-size:12.5px;color:#cfd9e2}.lx .ab{display:block;font-size:11.5px;color:#8b9aab;margin-top:2px}
.lr{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin-top:6px}
.lr a,.lr span.x{font-size:11px;padding:1px 6px;border-radius:6px;background:#151c25;border:1px dashed #2f4256;color:#b9c6d2;text-decoration:none;overflow-wrap:anywhere}
.ol{list-style:none;display:grid;gap:0}
.ol li{display:grid;grid-template-columns:22px minmax(0,1fr);gap:6px;padding:6px 0;border-bottom:1px solid #1a2532;font-size:12.5px;color:#dbe4ec;scroll-margin-top:70px}
.ol li:last-child{border-bottom:0}.ol li:target{background:rgba(29,155,240,.12);border-radius:6px}
.ol .n{font-size:11px;color:#6f8294;font-weight:800;text-align:right;padding-top:1px}
.ol .a{display:block;color:var(--mint);font-size:12px;margin-top:1px}.ol .a.s{color:#9aa8b6}.ol .a.x{color:var(--red)}
.ol code{font-size:10px;color:#6f8294;overflow-wrap:anywhere}
.ol .k{font-size:10px;font-weight:800;border-radius:5px;padding:0 5px;margin-right:4px}
.k.skip{background:rgba(140,154,168,.12);color:#9aa8b6}.k.lab{background:rgba(255,184,77,.14);color:var(--amber)}
.k.sus{background:rgba(255,92,108,.15);color:var(--red)}.k.chk{background:rgba(29,155,240,.15);color:#8fcbff}
.fl .st{font-size:10px;font-weight:800;border-radius:5px;padding:0 5px;margin-left:4px}
.st.on{background:rgba(61,255,168,.12);color:var(--on)}.st.off{background:rgba(140,154,168,.12);color:#9aa8b6}.st.al{background:rgba(29,155,240,.14);color:#8fcbff}
.pv{display:inline-block;font-size:10.5px;padding:0 5px;margin:2px 3px 0 0;border-radius:5px;background:#151c25;border:1px dashed #2f4256;color:#b9c6d2}
.pv b{color:#e8f4ff}
@media(max-width:430px){.sv{grid-template-columns:1fr 1fr 1fr}.sv b{font-size:11.5px}}
"""

SURF = [("TIMELINE_HOME", "팔로워 피드", "내가 팔로우한 계정의 글이 홈에 나올 때 쓰는 규칙이에요 (home-mixer가 팔로우 중인 글에 TimelineHome 규칙을 써요)"),
        ("TIMELINE_HOME_RECOMMENDATIONS", "비팔로워 추천", "팔로우하지 않은 사람의 '추천' 피드에 나올 때 쓰는 규칙이에요 (TimelineHomeRecommendations)"),
        ("NOTIFICATIONS_WRITER_V2_MENTION", "답글·멘션 알림", "누군가에게 답글·멘션 알림이 갈 때 쓰는 규칙이에요 (NOTIFICATIONS_WRITER_V2_MENTION, 답글도 같은 규칙)")]
ACT = {"drop_post": ("숨김", "hide"), "tombstone": ("삭제 표시", "hide"), "blur": ("가림", "blur"),
       "blur_with_age_prompt": ("가림(나이 확인)", "blur"), "limit": ("제한", "blur"),
       "label_interstitial": ("경고 화면", "blur"), "legacy_nsfw_interstitial": ("경고 화면", "blur"),
       "soft_intervention": ("안내", "blur"), "appealable": ("이의 신청형", "blur")}
AUD = {"NonFollowers": "팔로워가 아닌 사람에게만", "NonAuthors": "작성자 본인 빼고 모두에게", "Everyone": "모두에게", "OnlyAuthor": "작성자에게만"}
POLICY = {"PlatformManipulation": "플랫폼 조작", "Cse": "아동 성착취"}


def snap_get(snap, key):
    for d in ("switches", "other", "weights"):
        v = (snap or {}).get(d, {}).get(key)
        if v is not None:
            return v
    return None


def render_limits(ctx):
    src = ctx["src"]
    snap = ctx.get("snap") or {}
    ko = load_ko()
    KT, KL, KS, KB, KF, KV = (ko.get(k, {}) for k in ("text", "label", "score", "bot", "filter", "vf"))
    def tr(t):
        return KT.get(t)
    def lname(raw):
        e = KL.get(P.norm(raw))
        return e[0] if e else raw

    post_rules = P.parse_rules(P.rd(src, P.ENF_POST))
    user_rules = P.parse_rules(P.rd(src, P.ENF_USER))
    safety = P.parse_safety(P.rd(src, P.SAFETY))
    ceiling = P.follower_ceiling(P.rd(src, P.CEIL))
    uth = P.parse_uth(P.rd(src, P.UTH))
    bots = P.parse_bots(src)
    vf = P.parse_vf(src)
    flt = P.parse_filters(src)

    out = []
    A = out.append
    A('<section class="tab lim" id="t-limits"><h2 class="th2">노출 제한 · 라벨 · 자동 조치</h2>'
      f'<div class="note">최신 커밋 <b>{esc(ctx["latest"]["sha"][:7])}</b> 기준 · 코드에 적힌 규칙을 그대로 읽어서 만들어요. 규칙이 바뀌거나 없어지면 이 탭도 자동으로 바뀌어요</div>'
      '<div class="warn">⚠️ <b>공개 코드 기본값 기준</b>이에요. 실제 서비스에 똑같이 적용되는지는 확인할 수 없어요. 판정 모델의 점수 기준(몇 점이면 스팸인지 등)은 대부분 공개되지 않았어요. 순위·노출 이야기이고 <b>수익 단가와는 별개</b>예요</div>')

    # ---------- 라벨 모음
    labels = {}  # (kind, norm) -> dict
    def L(kind, raw):
        k = (kind, P.norm(raw))
        if k not in labels:
            labels[k] = dict(kind=kind, raw=raw, uth=None, rules=[], surf={})
        return labels[k]
    if uth:
        for x in uth.get("postLabels", []):
            L("post", x["key"])["uth"] = x
        for x in uth.get("accountLabels", []):
            L("user", x["key"])["uth"] = x
    rule_cnt = 0
    for kind, rules, tag in (("post", post_rules, "글"), ("user", user_rules, "계정")):
        for r in rules or []:
            for lab in r["labels"]:
                L(kind, lab)["rules"].append((f"#r-{kind}-{r['id']}", f"{tag} 규칙 {r['id']}"))
    for b in bots or []:
        for lab in b["post"]:
            L("post", lab)["rules"].append((f"#b-{b['name']}", f"봇 {b['id']}"))
        for lab in b["user"]:
            L("user", lab)["rules"].append((f"#b-{b['name']}", f"봇 {b['id']}"))
    if vf:
        for lvl, _, _ in SURF:
            lv = vf["levels"].get(lvl)
            if not lv:
                continue
            for n in lv["user"] + lv["post"]:
                d = vf["defs"][n]
                for lab in d["labels"]:
                    kind = "user" if d["kind"] == "user" else "post"
                    e = L(kind, lab)
                    if lvl not in e["surf"]:
                        e["surf"][lvl] = d

    def surf_html(e):
        cells = []
        for lvl, nm, why in SURF:
            if not vf or lvl not in vf["levels"]:
                cells.append(f'<div class="none"><span class="sl">{nm}</span><b>확인 불가</b></div>')
                continue
            d = e["surf"].get(lvl)
            if not d:
                cells.append(f'<div class="none tip"{tip(why + " · 이 목록에 이 라벨 규칙이 없어요")}><span class="sl">{nm}</span><b>규칙 없음</b></div>')
                continue
            a, cls = ACT.get(d["action"], (d["action"], "blur"))
            aud = AUD.get(d["audience"], d["audience"])
            cells.append(f'<div class="{cls} tip"{tip(f"{why} · {aud} {a} · 규칙 {d["id"]}")}><span class="sl">{nm}</span><b>{a}</b></div>')
        return '<div class="sv">' + "".join(cells) + '</div>'

    def lcard(e):
        raw, kind = e["raw"], e["kind"]
        ko_name = lname(raw)
        h = [f'<div class="lc" id="l-{kind}-{esc(P.norm(raw))}"><div class="lh"><h4>{esc(ko_name)}</h4>'
             f'<span class="lk">{esc(raw)}</span><span class="lt">{"글 라벨" if kind == "post" else "계정 라벨"}</span></div>']
        h.append(surf_html(e))
        if e["uth"]:
            eff, ab = e["uth"]["effect"], e["uth"]["about"]
            h.append(f'<div class="lx"><b>X 설명</b> {esc(tr(eff) or eff)}<span class="ab">{esc(tr(ab) or ab)}</span></div>')
        else:
            h.append('<div class="lx"><span class="ab">X의 Under the Hood 공개 목록에는 없는 라벨이라 공식 설명이 없어요</span></div>')
        if e["rules"]:
            h.append('<div class="lr"><span class="bl">붙이는 규칙</span>' + "".join(f'<a href="{esc(a)}">{esc(t)}</a>' for a, t in dict.fromkeys(e["rules"])) + '</div>')
        h.append('</div>')
        return "".join(h)

    main_l = [e for e in labels.values() if e["rules"]]
    main_l.sort(key=lambda e: (-len(e["rules"]), e["kind"] != "user"))
    rest_l = [e for e in labels.values() if not e["rules"] and (e["uth"] or e["surf"])]

    # ---------- 요약
    shr = [e for e in labels.values() if P.norm(e["raw"]) == "SPAMHIGHRECALL"]
    shr_rules = sum(len(dict.fromkeys(e["rules"])) for e in shr)
    rec_only = [e for e in labels.values() if "TIMELINE_HOME_RECOMMENDATIONS" in e["surf"] and "TIMELINE_HOME" not in e["surf"]
                and e["surf"]["TIMELINE_HOME_RECOMMENDATIONS"]["action"] == "drop_post"]
    both = [e for e in labels.values() if e["surf"].get("TIMELINE_HOME", {}).get("action") == "drop_post"]
    sum_start = len(out)
    A('<div class="card"><div class="ch3"><h3>👀 한눈에</h3></div><ul class="sum">')
    if shr:
        A(f'<li><b>스팸 의심(SpamHighRecall)</b> 라벨을 붙이는 자동 규칙이 <b>{shr_rules}개</b> 있어요 (글·계정 합계)</li>')
    if vf:
        A(f'<li>팔로워가 아닌 사람의 <b>추천에서만</b> 빠지게 하는 라벨 <b>{len(rec_only)}개</b> · 팔로워 피드에서도 숨기는 라벨 <b>{len(both)}개</b></li>')
        e = labels.get(("post", "SPAMHIGHRECALL"))
        if e and "TIMELINE_HOME_RECOMMENDATIONS" in e["surf"] and "TIMELINE_HOME" not in e["surf"]:
            A('<li>스팸 의심 라벨이 붙은 글도 <b>팔로워 피드 규칙 목록에는 없어요</b>. 대신 비팔로워 추천에서 빠져요</li>')
    if flt and flt.get("max_post_age"):
        A(f'<li>추천 후보는 작성된 지 <b>{secs_ko(flt["max_post_age"])}</b>이 지나면 빠져요 (AgeFilter)</li>')
    cs = snap_get(snap, "home-mixer:EnableViewerColdStart")
    if cs is not None:
        cap = snap_get(snap, "home-mixer:ColdStartFollowerCap")
        A(f'<li>팔로워 {esc(cap)}명 이하 작성자의 새 글을 한 자리 끌어올리는 장치(콜드 스타트)는 기본값 <b>{"ON" if cs else "OFF"}</b>이에요</li>')
    if len(out) == sum_start + 1:
        out.pop()
    else:
        A('</ul></div>')

    # ---------- 1. 라벨
    if labels:
        A('<h3 class="sh">🏷️ 라벨이 붙으면 어디서 숨겨지나</h3>'
          '<div class="note">칸 3개는 visibility-filtering의 규칙 목록이에요. <b>숨김</b>=그 자리에 안 나와요 · <b>가림</b>=경고 뒤에 보여요 · <b>규칙 없음</b>=그 목록엔 이 라벨 규칙이 없어요(다른 곳 영향은 별개). 칸을 누르면 누구에게 적용되는지 나와요</div>')
        A('<div class="lg">' + "".join(lcard(e) for e in main_l) + '</div>')
        if rest_l:
            A(f'<details class="rest"><summary>자동 규칙 파일에 안 나오는 라벨 {len(rest_l)}개 더 보기 (성인물·신고·법적 차단 등)</summary><div class="lg">'
              + "".join(lcard(e) for e in rest_l) + '</div></details>')
        tk = []
        for grp, nm in (("postTakedowns", "글"), ("accountTakedowns", "계정")):
            for x in (uth or {}).get(grp, []):
                key = re.sub(r"\(.*\)", "", x["key"])
                tk.append(f'<li><b>{esc(lname(key))}</b> <span class="lk">{esc(x["key"])}</span> {nm} · {esc(tr(x["effect"]) or x["effect"])}</li>')
        if tk:
            A(f'<details class="rest"><summary>법적 차단·저작권 표시 {len(tk)}개 보기</summary><ul class="sum" style="margin-top:6px">' + "".join(tk) + '</ul></details>')
        A(src_line(P.UTH if uth else None, P.VF_LEVELS if vf else None, P.VF_TWEET if vf else None, P.VF_AUTHOR if vf else None))

    # ---------- 2. abuse-enforcement 규칙
    def cond_ko(r):
        w = r["when"]
        bits = []
        scores = re.findall(r'(\w+)"?\s+in\s+score\.labels', w)
        neg = re.findall(r'!\(\s*"?(\w+)"?\s+in\s+score\.labels\s*\)', w)
        pos = [s for s in scores if s not in neg]
        for s in pos:
            bits.append(esc(KS.get(s, s)))
        for s in neg:
            if s == "enforcement_threshold_reached":
                bits.append("단, 이미 조치 기준에 도달한 경우는 빼요")
            else:
                bits.append(f"단, {esc(s)} 판정은 빼요")
        if re.search(r'"?(\w+)"?\s+in\s+user\.labels', w):
            bits.append("그리고 계정에 이미 " + ", ".join(esc(lname(x)) for x in re.findall(r'"?(\w+)"?\s+in\s+user\.labels', w)) + " 라벨이 있음")
        if "allowlist" in w:
            bits.append("예외 목록(allowlist)에 있는 " + ("글" if "post_allowlist" in w else "계정"))
        if "!user.present" in w:
            bits.append("작성자 정보를 찾을 수 없음")
        if "cred.follower_count" in w:
            v = re.search(r"follower_count\s*>=\s*([\d.]+)", w)
            bits.append(f"팔로워 수가 기준 이상 (코드 값 {esc(v.group(1)) if v else '?'}" + (", 파일 주석상 '조작 방지용 가짜 값'이라 실제 기준은 비공개)" if r["mock"] else ")"))
        if "cred.is_high" in w or "cred.score" in w:
            v = re.search(r"cred\.score\s*>=\s*([\d.]+)", w)
            bits.append(f"계정 신뢰도(PageRank)가 높음 (코드 값 {esc(v.group(1)) if v else '?'}도 가짜 값으로 보이고 실제 기준은 비공개)")
        if "skip_author_credibility_prechecks" in w:
            bits.append("판정이 '신뢰도 예외 끄기'를 요청하면 이 예외는 적용 안 돼요")
        if w.strip() in ("user.suspended",):
            bits.append("이미 정지된 계정")
        if w.strip() in ("user.deactivated",):
            bits.append("이미 비활성화된 계정")
        if w.strip() == "true":
            bits.append("이 서비스까지 넘어온 " + ("글" if r.get("_kind") == "post" else "계정") + " 중 위 규칙에 하나도 안 걸린 경우 (마지막 기본 규칙)")
        return " · ".join(bits) if bits else f"조건 {code(w)}"

    def act_ko(r, kind):
        ks = [k for k in r["kinds"] if k != "act_all"]
        if ks == ["skip"]:
            return ("skip", "예외", "조치 없이 끝 · 아래 규칙은 안 봐요")
        parts, cls = [], "chk"
        for k in ks:
            if k in ("act_add_post_labels_v2", "act_add_labels_v2"):
                d = days(r["ttl"][0]) if r["ttl"] else None
                parts.append(("글" if kind == "post" else "계정") + "에 " + ", ".join(lname(x) for x in r["labels"]) + " 라벨 " + (f"{d}" if d else "(기간 지정 없음)"))
                cls = "lab"
            elif k == "act_suspend_user":
                perm = r["perm"][0] if r["perm"] else None
                pol = POLICY.get(r["policy"][0], r["policy"][0]) if r["policy"] else "?"
                parts.append(("영구 정지" if perm == "true" else "계정 정지 (영구 아님)") + f" · 정책: {pol}")
                cls = "sus"
            elif k == "act_spam_liveness_check":
                parts.append("사람인지 확인(liveness) 요구")
            elif k == "act_captcha":
                parts.append("캡차 요구")
            elif k == "act_arkose":
                parts.append("Arkose 보안 퍼즐 요구")
            else:
                parts.append(k)
        label = {"lab": "라벨", "sus": "정지", "chk": "확인"}[cls]
        return (cls, label, " + ".join(parts))

    def rules_card(rules, kind, title, rel):
        if not rules:
            return
        A(f'<div class="card"><div class="ch3"><h3>{title}</h3><span class="mini">위에서부터 차례로 보고 처음 맞는 규칙 하나만 적용</span></div><ol class="ol">')
        for i, r in enumerate(rules, 1):
            r["_kind"] = kind
            cls, lab, act = act_ko(r, kind)
            A(f'<li id="r-{kind}-{esc(r["id"])}"><span class="n">{i}</span><div><span class="k {cls}">{lab}</span>{cond_ko(r)}'
              f'<span class="a{" s" if cls == "skip" else (" x" if cls == "sus" else "")}">→ {esc(act)}</span><code>{esc(r["id"])}</code></div></li>')
        A('</ol>' + src_line(rel) + '</div>')

    if post_rules or user_rules:
        A('<h3 class="sh">🤖 자동 조치 규칙 <span class="mini">abuse-enforcement-service</span></h3>'
          '<div class="note">판정 모델이 붙인 이름(score label)을 보고 라벨·정지·확인을 정해요. <b>어떤 글이 그 판정을 받는지(모델 기준)는 공개 코드에 없어요.</b> 설명은 판정 이름을 풀어 쓴 거예요</div>')
        A('<div class="lg">')
        rules_card(post_rules, "post", "📝 글 규칙", P.ENF_POST)
        rules_card(user_rules, "user", "👤 계정 규칙", P.ENF_USER)
        A('</div>')
        if safety:
            A('<div class="card"><div class="ch3"><h3>🛡️ 코드에 박힌 예외</h3><span class="mini">위 규칙과 별도로 서비스 코드가 먼저 확인</span></div><ul class="sum">')
            for s in safety:
                t = tr(s["when"]) or s["when"]
                extra = ""
                if "follower" in s["when"] and ceiling:
                    extra = f' <span class="mini">(코드 값 {ceiling:g} · 규칙 파일의 가짜 기준값처럼 실제 값이 아닐 수 있어요)</span>'
                if s["id"].startswith("invited_reply") and not s["id"].endswith("unknown"):
                    extra += ' <span class="mini">· <a href="#tips">크리에이터 팁</a> 탭 참고</span>'
                A(f'<li id="s-{esc(s["id"])}">{esc(t)}{extra} <code style="font-size:10px;color:#6f8294">{esc(s["reason"])}</code></li>')
            A('</ul>' + src_line(P.SAFETY, P.CEIL if ceiling else None) + '</div>')

    # ---------- 3. botmaker
    if bots:
        A('<h3 class="sh">🧹 실시간 라벨 봇 <span class="mini">botmaker-rules (scarecrow)</span></h3>'
          '<div class="note">글 작성·링크 판정·팔로우 같은 이벤트가 생길 때 바로 도는 규칙이에요. 링크 판정(BAD·LOW_QUALITY·UNSAFE)은 X의 링크 평판 시스템 값이고 기준은 공개되지 않았어요</div><div class="lg">')
        for b in bots:
            t = KB.get(b["name"])
            title, when = (t[0], t[1]) if t else (b["name"], "설명 준비 중이에요. 코드 이름 그대로 보여드려요")
            raw = P.rd(src, os.path.join(P.BOTS, b["file"])) or ""
            cond = raw.split("condition:", 1)[-1].split("action:", 1)[0] if "condition:" in raw else ""
            body = raw.split("action:", 1)[-1] if "action:" in raw else ""
            th = re.findall(r"(:?\w+)\s*(>=|>)\s*(0\.\d+)", cond + body)
            ch = []
            for lab in b["post"]:
                ch.append(f'<a href="#l-post-{P.norm(lab)}">글: {esc(lname(lab))}</a>')
            for lab in b["user"]:
                ch.append(f'<a href="#l-user-{P.norm(lab)}">계정: {esc(lname(lab))}</a>')
            if b["dynamic"]:
                ch.append('<span class="x">글: 링크 판정에 따른 라벨</span>')
            if b["removes"]:
                ch.append(f'<span class="x">판정이 풀리면 떼요</span>')
            if not ch:
                ch.append('<span class="x">글·계정 라벨을 직접 안 붙여요</span>')
            meta = []
            meta.append(f'기간 <b>{days(b["dur"])}</b>' if b["dur"] else '기간 <b>지정 없음</b>')
            for v in dict.fromkeys(f"{n.lstrip(':')} {op} {x}" for n, op, x in th):
                meta.append(f'<b>{esc(v)}</b>')
            sk = []
            if "IsHighPageRankUser" in b["skips"]:
                sk.append("신뢰도(PageRank) 높은 계정")
            if "IsUserGrayVerified" in b["skips"]:
                sk.append("회색 인증 계정")
            if "AutoExpiringTempSkipList" in b["skips"]:
                sk.append("임시 예외 목록")
            if b["test_skip"]:
                sk.append("테스트 계정")
            act = "" if b["active"] == "true" else f' <span class="lt">isActive: {esc(b["active"])}</span>'
            A(f'<div class="lc" id="b-{esc(b["name"])}"><div class="lh"><h4>{esc(title)}</h4><span class="lk">bot {esc(b["id"])}</span>{act}</div>'
              f'<div class="lx">{esc(when)}</div><div class="lr"><span class="bl">결과</span>{"".join(ch)}</div>'
              f'<div class="lr"><span class="bl">값</span>' + "".join(f'<span class="pv">{m}</span>' for m in meta) + '</div>'
              + (f'<div class="lr"><span class="bl">제외</span><span class="x">{" · ".join(sk)}</span></div>' if sk else '')
              + src_line(f'{P.BOTS}/{b["file"]}') + '</div>')
        A('</div>')

    # ---------- 4. 필터
    FP = {
        "AgeFilter": ([], None),
        "NewUserSoftNsfwFilter": (["NewUserSoftNsfwFilterMaxAccountAgeSecs:s", "NewUserSoftNsfwFilterMaxScoringSeqLength"], "EnableNewUserSoftNsfwFilter"),
        "OONRetweetReplyFilter": (["EnablePhoenixOonReplies", "PhoenixOonRepliesRootOnly"], None),
        "OONNsfwSimclustersFilter": ([], "EnableSimclustersSource"),
        "NewUserMinEngagementFilter": (["NewUserMinEngagementFilterMaxAccountAgeSecs:s", "NewUserMinEngagementFilterMaxResurrectionAgeSecs:s", "NewUserMinEngagementFilterMetric", "NewUserMinEngagementFilterUseRatio", "NewUserMinEngagementThreshold"], "EnableNewUserMinEngagementFilter"),
        "InventoryHoldoutFilter": (["InventoryHoldoutOriginalsPercent", "InventoryHoldoutRepliesPercent", "InventoryHoldoutRetweetsPercent"], "EnableInventoryHoldout"),
        "FavHoldoutFilter": ([], "EnableFavHoldout"),
        "ZeroFavCodivertFilter": ([], "ViewerZeroFavCodivertIsTreatment"),
        "PreviouslyServedPostsFilter": (["EnableServedFilterAllRequests"], None),
        "FairShareRankingFilter": (["PhoenixScoresResultSize"], "EnableFairShareRanking"),
        "VideoCarouselFilter": ([], "EnableVideoCarousel"),
    }
    COND = {"VideoFilter": "앱이 요청할 때만", "AncestorVideoFilter": "앱이 요청할 때만", "TopicIdsFilter": "주제 피드·제외 주제가 있을 때만",
            "ViewerMutedKeywordFilter": "뮤트 단어가 있을 때만"}

    def frow(i, st, elsewhere=False):
        t = KF.get(st)
        name, desc = (t[0], t[1]) if t else (st, "설명 준비 중이에요")
        sp = FP.get(st, ([], None))
        state = '<span class="st al">항상</span>'
        if sp[1]:
            v = snap_get(snap, "home-mixer:" + sp[1])
            state = f'<span class="st {"on" if v else "off"} tip"{tip(sp[1] + " 기본값")}>{"ON" if v else "OFF"}</span>' if v is not None else '<span class="st off">?</span>'
        elif elsewhere:
            state = '<span class="st off">다른 파이프라인</span>'
        elif st in COND:
            state = f'<span class="st al">{COND[st]}</span>'
        pv = []
        if st == "AgeFilter" and flt.get("max_post_age"):
            pv.append(f'<span class="pv">MAX_POST_AGE <b>{secs_ko(flt["max_post_age"])}</b></span>')
        for p in sp[0]:
            nm, _, unit = p.partition(":")
            v = snap_get(snap, "home-mixer:" + nm)
            if v is None:
                continue
            vs = secs_ko(v) if unit == "s" else ("ON" if v is True else "OFF" if v is False else str(v).strip('"'))
            pv.append(f'<span class="pv">{esc(nm)} <b>{esc(vs)}</b></span>')
        if st == "FavHoldoutFilter":
            pv.append('<span class="pv">좋아요 많을수록 보류 비율 ↑ <b>최대 15%</b></span>')
        return (f'<li><span class="n">{i}</span><div><b>{esc(name)}</b>{state}<span class="a s" style="color:#cfd9e2">{esc(desc)}</span>'
                + ("".join(pv) and f'<div>{"".join(pv)}</div>') + f'<code>{esc(st)}</code></div></li>')

    if flt:
        fy, fo = flt["wired"]["foryou"], flt["wired"]["following"]
        known = set(flt["structs"].values())
        A('<h3 class="sh">🚧 피드 후보 필터 <span class="mini">home-mixer</span></h3>'
          '<div class="note">점수를 매기기 전·후에 후보에서 빼는 단계예요. <b>ON/OFF</b>는 스위치 기본값이고, <b>항상</b>은 스위치 없이 늘 돌아요</div><div class="lg">')
        if fy:
            A('<div class="card fl"><div class="ch3"><h3>✨ 추천(For You) 피드</h3><span class="mini">코드에 적힌 순서</span></div><ol class="ol">'
              + "".join(frow(i, s) for i, s in enumerate(fy, 1)) + '</ol>' + src_line(P.HM_PIPE) + '</div>')
        if fo:
            A('<div class="card fl"><div class="ch3"><h3>👥 팔로잉 피드</h3><span class="mini">코드에 적힌 순서</span></div><ol class="ol">'
              + "".join(frow(i, s) for i, s in enumerate(fo, 1)) + '</ol>' + src_line(P.HM_FOLLOW) + '</div>')
        other = [s for s in flt["structs"].values() if s and s not in fy and s not in fo]
        if other:
            A('<div class="card fl"><div class="ch3"><h3>🧩 그 밖의 필터</h3><span class="mini">위 두 파이프라인 파일 밖에서 쓰여요</span></div><ol class="ol">'
              + "".join(frow(i, s, True) for i, s in enumerate(other, 1)) + '</ol>' + src_line(P.HM_FILTERS + "/") + '</div>')
        A('</div>')

    # ---------- 5. 기타
    cards = []
    if snap_get(snap, "home-mixer:EnableViewerColdStart") is not None:
        g = lambda n: snap_get(snap, "home-mixer:" + n)
        on = g("EnableViewerColdStart")
        lo, hi = g("ColdStartSlotMin"), g("ColdStartSlotMax")
        try:
            slot = f"{int(lo) + 1}번째" if int(hi) - int(lo) == 1 else f"{int(lo) + 1}~{int(hi)}번째 중 무작위"
        except (TypeError, ValueError):
            slot = "?"
        try:
            prior = f"{float(g('ColdStartBetaAlpha0')) / (float(g('ColdStartBetaAlpha0')) + float(g('ColdStartBetaBeta0'))) * 100:.1f}%"
        except (TypeError, ValueError, ZeroDivisionError):
            prior = "?"
        cards.append(
            f'<div class="lc"><div class="lh"><h4>🌱 작은 계정 새 글 끌어올리기 (콜드 스타트)</h4><span class="st {"on" if on else "off"}">{"ON" if on else "OFF"}</span></div><ul class="sum">'
            f'<li>피드 요청 1번마다 조건에 맞는 글 <b>1개</b>를 점수 순위 <b>{slot}</b> 자리 점수까지 올려요 (원래 더 높으면 그대로)</li>'
            f'<li>조건: <b>답글·리포스트가 아닌 원글</b> · 작성자 팔로워 <b>{esc(g("ColdStartFollowerCap"))}명 이하</b> · 작성 <b>{secs_ko(g("ColdStartMaxPostAgeSecs"))} 이내</b> · 홈 노출 <b>{esc(g("ColdStartImpressionThreshold"))}회 미만</b> · 원래 순위가 0점 아닌 후보 중 상위 <b>{float(g("LowImpressionsMaxPositionRatio") or 0) * 100:g}%</b> 안</li>'
            + (f'<li>여러 개면 <b>좋아요 ÷ 홈 노출</b>로 운을 섞어 뽑고(톰슨 샘플링, 출발점 좋아요율 {prior}), 상위 {esc(g("ColdStartTsTopK"))}개 중 점수 높은 글을 골라요</li>' if g("EnableColdStartThompsonSampling") else '<li>여러 개면 점수가 가장 높은 글을 골라요</li>')
            + '<li>작성자·보는 사람 실험군에 따라 대상이 나뉘어요</li></ul>'
            + src_line("home-mixer/scorers/author_cold_start.rs", "home-mixer/params/param.rs") + '</div>')
    oon = snap_get(snap, "vm-ranker:OonWeightFactor")
    if oon is not None:
        nu, nut = snap_get(snap, "vm-ranker:NewUserOonWeightFactor"), snap_get(snap, "vm-ranker:NewUserAgeThresholdSecs")
        extra = ""
        try:
            if nut is not None and float(nut) == 0:
                extra = f'<li>새 가입자용 배율(<b>{esc(num(nu))}</b>)도 있지만 기준 나이(NewUserAgeThresholdSecs)가 <b>0초</b>라 기본값으로는 아무도 해당되지 않아요</li>'
            elif nut is not None:
                extra = f'<li>가입 {secs_ko(nut)} 안 된 사람에게는 배율 <b>{esc(num(nu))}</b>를 써요 (팔로우 5명 이상일 때)</li>'
        except ValueError:
            pass
        cards.append(
            f'<div class="lc"><div class="lh"><h4>🌍 비팔로워 글 점수 배율</h4><span class="lk">OonWeightFactor</span></div><ul class="sum">'
            f'<li>팔로우하지 않은 계정의 글은 최종 점수에 <b>× {esc(oon)}</b>를 곱해요. 같은 예측이면 팔로워 글보다 노출 순위가 낮아요</li>'
            f'<li>주제 피드에서는 × <b>{esc(snap_get(snap, "vm-ranker:TopicOonWeightFactor"))}</b></li>{extra}'
            '<li>vm-ranker 기본값이에요. home-mixer 쪽 점수 계산에 같은 값이 쓰이는지는 코드로 확인하지 못했어요</li></ul>'
            + src_line("vm-ranker/params.rs", "vm-ranker/scoring/value_model.rs", "xai-value-model/scoring.rs") + '</div>')
    if cards:
        A('<h3 class="sh">⚖️ 그 밖에 노출에 영향 주는 값</h3><div class="lg">' + "".join(cards) + '</div>')

    A('<div class="note" style="margin-top:8px">빠진 것: 판정 모델 자체(어떤 글이 스팸·저품질 점수를 받는지), 검색·알림의 세부 규칙, 실제 서비스 설정값은 공개 코드에 없거나 이 탭 범위 밖이에요</div>')
    A('</section>')
    return "".join(out)
