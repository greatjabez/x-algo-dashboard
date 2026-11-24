"""소스 파서: 노출 제한 탭용. 표준 라이브러리만 사용."""
import os, re

ENF_POST = "abuse-enforcement-service/service-lib/rules/enforcement_post.yaml"
ENF_USER = "abuse-enforcement-service/service-lib/rules/enforcement_user.yaml"
SAFETY = "abuse-enforcement-service/service-lib/src/safety_checks.rs"
CEIL = "abuse-enforcement-service/types/src/action_control.rs"
UTH = "under-the-hood/strato/lib/underTheHoodLabels.strato"
BOTS = "botmaker-rules/scarecrow/bot"
VF_LEVELS = "visibility-filtering/rules/levels.rs"
VF_TWEET = "visibility-filtering/rules/tweet_rules.rs"
VF_AUTHOR = "visibility-filtering/rules/author_rules.rs"
HM_PIPE = "home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs"
HM_FOLLOW = "home-mixer/candidate_pipeline/reverse_chron_posts_pipeline.rs"
HM_FILTERS = "home-mixer/filters"
HM_CONFIG = "home-mixer/params/config.rs"


def rd(src, rel):
    try:
        with open(os.path.join(src, rel), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def norm(label):
    """Under the Hood의 normalizeLabel과 같은 방식: 밑줄 없애고 대문자."""
    return re.sub(r"[^A-Za-z0-9]", "", label or "").upper()


# ---------------- abuse-enforcement YAML
def parse_rules(text):
    if not text:
        return None
    body = text.split("rules:", 1)[-1]
    blocks = re.split(r"\n\s*-\s+id:\s*", "\n" + body)[1:]
    out = []
    for b in blocks:
        rid = b.split("\n", 1)[0].strip().strip("'\"")
        m = re.search(r"\bwhen:\s*(>-?|\|-?)?\s*\n?(.*?)(?=\n\s*(?:kind|then|reason|action|actions|act|policy|labels|ttl_msec|perm)\s*:|\Z)", b, re.S)
        when = " ".join((m.group(2) if m else "").split()).strip("'\"") if m else ""
        kinds = re.findall(r"\bkind:\s*([\w]+)", b)
        labels = []
        for lm in re.finditer(r"labels:\s*\[([^\]]*)\]", b):
            labels += [x.strip().strip("'\"") for x in lm.group(1).split(",") if x.strip()]
        for lm in re.finditer(r"labels:\s*\n((?:\s*-\s*[\w\"']+\s*\n?)+)", b):
            labels += re.findall(r"-\s*['\"]?(\w+)", lm.group(1))
        ttl = [int(x.replace("_", "")) for x in re.findall(r"ttl_msec:\s*([\d_]+)", b)]
        perm = re.findall(r"\bperm\w*:\s*(true|false)", b)
        policy = re.findall(r"\bpolicy:\s*['\"]?(\w+)", b)
        reason = re.findall(r"\breason:\s*['\"]?([\w-]+)", b)
        mock = "mock" in b.lower()
        out.append(dict(id=rid, when=when, kinds=kinds, labels=labels, ttl=ttl,
                        perm=perm, policy=policy, reason=reason, mock=mock))
    return out


def parse_safety(text):
    if not text:
        return []
    out = []
    for m in re.finditer(r"pub const (\w+): SafetyCheck = SafetyCheck \{(.*?)\};", text, re.S):
        body = m.group(2)
        g = lambda k: (re.search(k + r':\s*"([^"]*)"', body) or [None, ""])[1]
        idm = re.search(r'id:\s*"([^"]*)"', body)
        out.append(dict(const=m.group(1), id=idm.group(1) if idm else m.group(1).lower(),
                        reason=g("reason"), when=g("when")))
    return out


def follower_ceiling(text):
    if not text:
        return None
    m = re.search(r'FOLLOWER_CEILING_CHECK[^{]*\{[^}]*when:\s*"[^"]*>=\s*([\d.]+)"', text)
    return float(m.group(1)) if m else None


# ---------------- Under the Hood
def parse_uth(text):
    if not text:
        return None
    res = {}
    for m in re.finditer(r"val (\w+)\s*=\s*Map\((.*?)\n\s*\)", text, re.S):
        name, body = m.group(1), m.group(2)
        items = []
        for e in re.finditer(r'"([^"]+)"\s*->\s*\{\s*about\s*=\s*"((?:[^"\\]|\\.)*)"\s*,\s*effect\s*=\s*"((?:[^"\\]|\\.)*)"', body):
            items.append(dict(key=e.group(1), about=e.group(2), effect=e.group(3)))
        if items:
            res[name] = items
    return res


# ---------------- botmaker
def parse_bots(src):
    d = os.path.join(src, BOTS)
    if not os.path.isdir(d):
        return None
    out = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".bot"):
            continue
        t = rd(src, os.path.join(BOTS, fn)) or ""
        def f(k):
            m = re.search(r"^" + k + r":\s*'?([^'\n]*)'?", t, re.M)
            return m.group(1).strip() if m else ""
        ev = re.search(r"event:\s*(\w+)", t)
        apply_post = re.findall(r'(?:TweetRtfApplyLabel|SetTweetRtfApplyLabelWithExpirationMs)\(\s*"(\w+)"', t)
        apply_user = re.findall(r'SetUserLabel\(\s*\w+\s*,\s*"(\w+)"', t)
        nsfw_user = re.findall(r'ApplyNsfwUserLabel(?:OrCreateReport)?\([^)]*?"(NSFW_\w+)"', t, re.S)
        if "ApplyNsfwUserLabel" in t and not nsfw_user:
            nsfw_user = sorted(set(re.findall(r'"(NSFW_(?:HIGH_PRECISION|HIGH_RECALL|NEAR_PERFECT))"', t)))
        removes = re.findall(r'TweetRtfRemoveLabel\(\s*"(\w+)"', t)
        dyn = "TweetRtfApplyLabel(:labelType" in t.replace(" ", "")
        dur = None
        m = re.search(r"CurrentTimeMs\(\)\s*\+\s*\(\s*(\w+)\s*(?:\*\s*(\d+))?\s*\)", t)
        if m:
            unit, mult = m.group(1), int(m.group(2) or 1)
            base = {"OneWeekInSecs": 7 * 86400000, "OneDayInMillis": 86400000, "OneDayInSecs": 86400000,
                    "DayInSecs": 86400000, "SevenDaysInSecs": 7 * 86400000, "ThirtyDaysInSecs": 30 * 86400000}.get(unit)
            if base:
                if unit.endswith("Secs") and mult == 1000:
                    mult = 1
                dur = base * mult
        skips = [k for k in ("IsHighPageRankUser", "IsUserGrayVerified", "IsUserGoldVerified", "AutoExpiringTempSkipList") if k in t]
        out.append(dict(file=fn, name=fn[:-4], id=f("id"), event=ev.group(1) if ev else "",
                        active=f("isActive") or "?", post=list(dict.fromkeys(apply_post)),
                        user=list(dict.fromkeys(apply_user + nsfw_user)), removes=list(dict.fromkeys(removes)),
                        dynamic=dyn, dur=dur, skips=skips, test_skip="IsTestUser" in t))
    return out


# ---------------- visibility filtering
def _rule_defs(text, kind):
    out = {}
    for m in re.finditer(r"pub\(super\) const (\w+): (?:User)?Rule(?:<[^>]*>)? = Rule \{(.*?)\n\};", text or "", re.S):
        body = m.group(2)
        g = lambda k: (re.search(k + r":\s*([^\n]*?),?\n", body) or [None, ""])[1].strip()
        when = re.search(r"when:\s*(.*?),\s*\n\s*action:", body, re.S)
        act = re.search(r"action:\s*(\w+)\(?([^\n]*)", body)
        labs = re.findall(r"(?:TweetHasLabel\(SafetyLabelType::|AuthorHasLabel\(AuthorLabel::)(\w+)", body)
        out[m.group(1)] = dict(const=m.group(1), id=g("id").replace("RuleId::", ""), audience=g("audience"),
                               when=" ".join(when.group(1).split()) if when else "",
                               action=act.group(1) if act else "", action_arg=(act.group(2) if act else "").strip(" ,"),
                               labels=labs, kind=kind)
    return out


def parse_vf(src):
    lv, tw, au = rd(src, VF_LEVELS), rd(src, VF_TWEET), rd(src, VF_AUTHOR)
    if not (lv and (tw or au)):
        return None
    defs = {**_rule_defs(tw, "post"), **_rule_defs(au, "user")}
    groups = {}
    for m in re.finditer(r"const (\w+): &\[&(?:dyn Listed|UserRule)\]\s*=\s*&\[(.*?)\];", lv, re.S):
        groups[m.group(1)] = re.findall(r"&?(\b[A-Z][A-Z0-9_]+\b)", m.group(2))
    groups.update({k: v for k, v in groups.items()})

    def expand(names, seen=()):
        res = []
        for n in names:
            if n in groups and n not in seen:
                res += expand(groups[n], seen + (n,))
            elif n in defs:
                res.append(n)
        return res

    levels = {}
    for m in re.finditer(r"pub\(super\) const (\w+): PostRules = PostRules \{(.*?)\n\};", lv, re.S):
        body = m.group(2)
        um = re.search(r"user:\s*(.*?)\n\s*post:", body, re.S)
        pm = re.search(r"post:\s*(.*)", body, re.S)
        levels[m.group(1)] = dict(
            user=expand(re.findall(r"\b([A-Z][A-Z0-9_]+)\b", um.group(1) if um else "")),
            post=expand(re.findall(r"\b([A-Z][A-Z0-9_]+)\b", pm.group(1) if pm else "")))
    return dict(defs=defs, levels=levels)


# ---------------- home-mixer filters
def parse_filters(src):
    d = os.path.join(src, HM_FILTERS)
    if not os.path.isdir(d):
        return None
    files = sorted(f[:-3] for f in os.listdir(d) if f.endswith(".rs") and f != "mod.rs")
    structs = {}
    for f in files:
        t = rd(src, os.path.join(HM_FILTERS, f + ".rs")) or ""
        m = re.search(r"pub struct (\w+Filter)\b", t)
        structs[f] = m.group(1) if m else None
    wired = {}
    for key, rel in (("foryou", HM_PIPE), ("following", HM_FOLLOW)):
        t = rd(src, rel) or ""
        wired[key] = re.findall(r"Box::new\((\w+Filter)\b", t)
    cfg = rd(src, HM_CONFIG) or ""
    m = re.search(r"MAX_POST_AGE:\s*u64\s*=\s*([\d\s*]+);", cfg)
    max_age = None
    if m:
        try:
            max_age = eval(m.group(1), {"__builtins__": {}})
        except Exception:
            max_age = None
    return dict(files=files, structs=structs, wired=wired, max_post_age=max_age)
