"""UI 冒烟：③ 钢琴卷帘下方的「导出简谱」。

只开浏览器 + stub 掉后端接口（不跑推理），验证两件事：

1. **正常路径**：点「导出简谱」→ 卷帘下方出现简谱区，里面是 1234567 的谱面；
2. **旧脚本兜底**：把卷帘实例上新增的三个方法（``getMeasures`` / ``activeTrackIndex``
   / ``secToPos``）删掉，模拟"浏览器缓存了旧 pianoroll.js"——
   必须**降级但仍能出谱、且不抛未捕获异常**，不能再出现"点了没反应"。

前置：服务已在跑（``./start.sh``）。运行::

    /tmp/pwenv/bin/python _smoke/check_jianpu_export.py [URL]
"""
from __future__ import annotations

import base64
import os
import re
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8777/"
FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   <- {detail}"))
    if not ok:
        FAILS.append(name)


TASK = {
    "task_id": "smoke_jp", "kind": "transcribe", "parent_id": None,
    "state": "done", "state_label": "已完成", "stage": "完成", "percent": 100.0,
    "audio_path": "/tmp/upload/测试曲.wav",
    "audio_original_name": "测试曲.wav",
    "result": {
        "key": "C:major", "key_cn": "C大调", "meter": "4/4", "bpm_int": 120,
        "duration": 16.0, "abc": "X:1\n", "sections": [],
        "chords": [
            {"start": 0.0, "end": 2.0, "label": "C:maj"},
            {"start": 2.0, "end": 4.0, "label": "A:min"},
            {"start": 4.0, "end": 6.0, "label": "F:maj"},
            {"start": 6.0, "end": 8.0, "label": "G:maj"},
        ],
        "tempo_map": [{"t": 0.0, "bpm": 120.0}],
        "vocal_notes": 7, "instrumental_notes": 0,
        "export": {"exports": [{"kind": "svp", "version": 153, "tracks": ["vocal"], "notes": 7}]},
    },
}

_MEASURES = [
    {"start": i * 2.0, "end": (i + 1) * 2.0, "score_start": float(i), "score_end": float(i + 1)}
    for i in range(8)
]
#: 第 1 小节故意塞满 16 个十六分音符：验证密集小节不会越出小节线、也不会相互重叠。
_SCALE = [60, 62, 64, 65, 67, 69, 71]
_NOTES = [(round(i * 0.125, 4), round((i + 1) * 0.125, 4), _SCALE[i % 7]) for i in range(16)] + [
    (2.0, 4.0, 67), (4.0, 5.0, 69), (5.0, 6.0, 71), (6.0, 8.0, 72),
    (8.0, 10.0, 60), (10.0, 12.0, 62), (12.0, 14.0, 64), (14.0, 16.0, 65),
]
ROLL = {
    "available": True, "source_abc": "score.abc", "voices_in_score": ["vocal"],
    "bpm": 120, "meter": "4/4", "beats_per_bar": 4, "beat_unit": 4, "unit_whole": 0.0625,
    "duration": 16.0, "tempo_map": [{"t": 0.0, "bpm": 120.0}],
    "measures": _MEASURES, "export_voices": ["vocal"], "warnings": [],
    "tracks": [{
        "voice": "vocal", "kind": "vocal", "display": "人声主旋律",
        "is_vocal": True, "editable": True,
        "notes": [{"start": s, "end": e, "pitch": p, "lyric": "la"} for s, e, p in _NOTES],
    }],
}


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.route("**/api/gpu", lambda r: r.fulfill(status=200, json={"available": False, "error": "无独显"}))
    page.route("**/api/state**", lambda r: r.fulfill(status=200, json={"busy": False, "task": TASK}))
    page.route("**/api/tasks/*/roll**", lambda r: r.fulfill(status=200, json=ROLL))
    page.route("**/api/audio/*", lambda r: r.fulfill(status=200, json={"available": False}))
    page.route("**/api/events**", lambda r: r.fulfill(status=200, content_type="text/event-stream", body=""))
    page.route("**/api/tasks/*/export-info", lambda r: r.fulfill(status=200, json={"files": []}))

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_selector("#jpExport:not([disabled])", timeout=10000)
    check("导出简谱按钮就绪（任务已完成）", True)

    # ---- 1) 正常路径 ----
    page.click("#jpExport")
    page.wait_for_selector("#jpPanel:not([hidden])", timeout=8000)
    sheet = page.inner_text("#jpSheet")
    meta = page.inner_text("#jpMeta")
    check("点「导出简谱」后卷帘下方出现简谱区", True)
    check("简谱区渲染出音符数字", any(ch in sheet for ch in "1234567"), repr(sheet[:80]))
    check("标题标出当前轨道", "人声主旋律" in page.inner_text("#jpTitle"), page.inner_text("#jpTitle"))
    check("谱面信息行给出 1 = C", "1 = C" in meta, meta)
    check("谱面上方有曲名", bool(page.inner_text("#jpSong").strip()), page.inner_text("#jpSong"))
    check("正常路径无未捕获异常", not errors, "; ".join(errors))

    # ---- 1b) 简谱下方的播放条 + 谱子跟着播放动起来 ----
    check("简谱下方有播放条（播放/进度/时间/音量）",
          all(page.query_selector(sel) for sel in ("#jpPlay", "#jpSeek", "#jpTime", "#jpVol")))
    check("简谱播放条已接到主走带条（复用同一路音频）",
          page.evaluate("() => typeof document.querySelector('#jpPlay').onclick === 'function'"))
    page.evaluate("() => seekToSeconds(4.0)")   # 4.0s 处是 A4（C 大调里的 6）
    page.wait_for_timeout(120)
    lit = page.eval_on_selector_all(".jp-tok.on", "els => els.map(e => e.innerText.trim())")
    check("seek 到 4s → 简谱有且只有一个记号被点亮", len(lit) == 1, repr(lit))
    check("点亮的正是那一刻的音（A4 → 6）", bool(lit) and "6" in lit[0], repr(lit))
    check("简谱播放条时间与主走带条一致",
          page.inner_text("#jpTime") == page.inner_text("#tpTime"),
          f'{page.inner_text("#jpTime")!r} vs {page.inner_text("#tpTime")!r}')

    # ---- 1b-2) 和弦行也有光标，且用不同颜色 ----
    page.evaluate("() => seekToSeconds(1.0)")
    page.wait_for_timeout(100)
    cur = page.evaluate(
        "() => { const c=document.querySelector('.jp-chord.on');"
        " const n=document.querySelector('.jp-tok.on'); if(!c) return null;"
        " const cs=getComputedStyle(c), ns=n?getComputedStyle(n):null;"
        " return {text:c.innerText.trim(),"
        "  count:document.querySelectorAll('.jp-chord.on').length,"
        "  bg:cs.backgroundColor, color:cs.color,"
        "  noteBg:ns?ns.backgroundColor:null}; }"
    )
    check("和弦行也有光标（同一时刻只有一个）", cur is not None and cur["count"] == 1, repr(cur))
    check("和弦光标颜色与旋律光标不同",
          bool(cur) and cur["bg"] != cur["noteBg"], repr(cur))

    page.evaluate("() => clearHighlight()")
    check("停止后高亮清空",
          page.eval_on_selector_all(".jp-tok.on, .jp-chord.on", "els => els.length") == 0)

    # ---- 1c) 版式规整：每行 4 小节、等宽、列线跨行对齐 ----
    geo = page.evaluate(
        "() => [...document.querySelectorAll('.jp-sys')]"
        ".map(s => [...s.querySelector('.jp-vrow').querySelectorAll('.jp-cell')]"
        ".map(c => c.getBoundingClientRect().width))"
    )
    lefts = page.evaluate(
        "() => [...document.querySelectorAll('.jp-sys')]"
        ".map(s => [...s.querySelector('.jp-vrow').querySelectorAll('.jp-cell')]"
        ".map(c => Math.round(c.getBoundingClientRect().left)))"
    )
    counts = [len(r) for r in geo]
    check("每排小节数一致（放不下自动换行）", bool(geo) and len(set(counts)) == 1, repr(counts))
    check("4/4 常规密度下每排 4 小节（每 4 拍一条线）", counts and counts[0] == 4, repr(counts))
    check("同一行内小节等宽", bool(geo) and all(max(r) - min(r) < 1.5 for r in geo), repr(geo))
    check("列线跨行对齐（每列左边 x 一致）",
          bool(lefts) and all(row == lefts[0] for row in lefts), repr(lefts))
    check("谱面完全不横向溢出（不需要左右滑）", page.evaluate(
        "() => { const s=document.querySelector('#jpSheet');"
        " return s.scrollWidth <= s.clientWidth + 1; }"))
    bars = page.evaluate(
        "() => { const row=document.querySelector('.jp-sys .jp-vrow');"
        " const cells=[...row.querySelectorAll('.jp-cell')];"
        " return {cells:cells.length,"
        "  left:cells.map(c=>parseFloat(getComputedStyle(c).borderLeftWidth)),"
        "  lastRight:parseFloat(getComputedStyle(cells[cells.length-1]).borderRightWidth)}; }"
    )
    check("每个小节都有左侧间隔线（|）", all(w > 0 for w in bars["left"]), repr(bars))
    check("每排末尾也有收尾线", bars["lastRight"] > 0, repr(bars))

    # ---- 1c-2) 两行声部：器乐旋律 + 和弦 ----
    voice_rows = page.evaluate(
        "() => [...document.querySelectorAll('.jp-sys')]"
        ".map(s => [...s.querySelectorAll('.jp-vrow')].map(r => r.querySelector('.jp-vname').innerText.trim()))"
    )
    check("每个 system 都有两行声部", bool(voice_rows) and all(len(r) == 2 for r in voice_rows), repr(voice_rows[:2]))
    check("第二行是「和弦」", bool(voice_rows) and all(r[1] == "和弦" for r in voice_rows), repr(voice_rows[:2]))
    chord_labels = page.eval_on_selector_all(".jp-chord", "els => els.map(e => e.innerText.trim())")
    check("和弦行按时间渲染出和弦名", chord_labels[:4] == ["C", "Am", "F", "G"], repr(chord_labels))

    # ---- 1c-2b) 每排开头的歌曲时间 mm:ss ----
    times = page.eval_on_selector_all(".jp-sys .jp-time", "els => els.map(e => e.innerText.trim())")
    check("每排开头都有 mm:ss 时间标注",
          bool(times) and all(re.fullmatch(r"\d{2}:\d{2}", t) for t in times), repr(times))
    check("第一排从 00:00 开始", bool(times) and times[0] == "00:00", repr(times[:3]))
    secs = [int(t.split(":")[0]) * 60 + int(t.split(":")[1]) for t in times if ":" in t]
    check("时间标注随排递增", all(b > a for a, b in zip(secs, secs[1:])), repr(times))

    # ---- 1c-2c) 简谱下方的钢琴键盘模拟 ----
    check("简谱下方有钢琴键盘模拟区", page.query_selector("#pianoView") is not None)
    pv = page.evaluate(
        "() => { const c=document.querySelector('#pianoView');"
        " return {w:c.width, h:c.height, notes:(S.pianoNotes||[]).length, range:S.pianoRange}; }"
    )
    check("钢琴区已绑定当前轨道音符", pv["notes"] > 0 and pv["range"] is not None, repr(pv))
    check("钢琴区画布尺寸有效", pv["w"] > 500 and pv["h"] >= 180, repr(pv))

    def pv_hash():
        return page.evaluate(
            "() => { const c=document.querySelector('#pianoView');"
            " const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;"
            " let h=0, ink=0;"
            " for(let i=0;i<d.length;i+=1600){ h=(h*31+d[i]+d[i+1]*3+d[i+2]*7)>>>0;"
            "   if(d[i]>60||d[i+1]>60||d[i+2]>60) ink++; }"
            " return {h:h, ink:ink}; }"
        )

    page.evaluate("() => seekToSeconds(0)")
    pv0 = pv_hash()
    page.evaluate("() => seekToSeconds(4)")
    pv4 = pv_hash()
    check("钢琴区确实绘制了键盘/音符（非空白）", pv0["ink"] > 50, repr(pv0))
    check("钢琴区随播放时间重绘（落键在动）", pv0["h"] != pv4["h"], f'{pv0} vs {pv4}')

    # ---- 1c-2d) 钢琴区也要演示和弦（琥珀色） ----
    pch = page.evaluate("() => (S.pianoChords||[]).map(n=>[n.pitch,n.start,n.end])")
    check("钢琴区包含和弦音（每和弦根音/三音/五音…）", len(pch) >= 6, f"{len(pch)} tones")
    page.evaluate("() => seekToSeconds(0.5)")     # C 和弦正在响
    amber = page.evaluate(
        "() => { const c=document.querySelector('#pianoView');"
        " const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;"
        " let n=0; for(let i=0;i<d.length;i+=4){"
        "  const r=d[i],g=d[i+1],b=d[i+2];"
        "  if(r>180 && g>95 && g<215 && b<95) n++; }"
        " return n; }"
    )
    check("钢琴区用琥珀色画出和弦音", amber > 30, f"amber={amber}")

    # ---- 1c-3) 右上角「下载图片」：整份谱面能画成 PNG ----
    check("右上角有「下载图片」按钮", page.query_selector("#jpPng") is not None)
    img = page.evaluate(
        "() => { const c=drawJianpuCanvas(S.jianpu); const ctx=c.getContext('2d');"
        " const d=ctx.getImageData(0,0,c.width,c.height).data; let ink=0;"
        " for(let i=0;i<d.length;i+=400){ if(d[i]<200 && d[i+1]<200 && d[i+2]<200) ink++; }"
        " return {w:c.width,h:c.height,ink:ink}; }"
    )
    check("导出图片为高清整谱（尺寸合理）", img["w"] >= 2000 and img["h"] >= 800, repr(img))
    check("导出图片里确实有谱面内容（非空白）", img["ink"] > 50, repr(img))
    if os.environ.get("SMOKE_PNG"):
        data_url = page.evaluate("() => drawJianpuCanvas(S.jianpu).toDataURL('image/png')")
        with open(os.environ["SMOKE_PNG"], "wb") as fp:
            fp.write(base64.b64decode(data_url.split(",", 1)[1]))

    # ---- 1d) 播放中：光标单向向前、最多点亮一个、暂停续播不跳回 ----
    page.evaluate("() => { buildPiano = async () => { throw new Error('force synth'); }; }")
    # 临时压矮谱面，强制出现纵向滚动，才能验证"光标不超过中间行"
    page.evaluate("() => { document.querySelector('#jpSheet').style.maxHeight='110px'; }")
    page.evaluate("() => seekToSeconds(9)")   # 第 5 小节：处在第 2 排，能验证自动纵向滚动
    page.click("#jpPlay")
    seq, tops = [], []
    for _ in range(60):                      # ~3s：第 5 小节起播，足够触发滚动又不至于放到结尾
        page.wait_for_timeout(50)
        seq.append(page.evaluate("() => [S.jpActive, document.querySelectorAll('.jp-tok.on').length]"))
        st = page.evaluate(
            "() => { const s=document.querySelector('#jpSheet');"
            " const on=document.querySelector('.jp-tok.on'); if(!on) return null;"
            " const br=s.getBoundingClientRect(), er=on.getBoundingClientRect();"
            " return {top: er.top-br.top, mid: s.clientHeight/2,"
            "         scrollTop: Math.round(s.scrollTop),"
            "         scrollable: s.scrollHeight > s.clientHeight+1}; }"
        )
        if st:
            tops.append(st)
    mid = page.evaluate("() => S.jpActive")
    page.evaluate("() => stopMelody()")
    off = page.evaluate("() => melodyOffset")
    page.click("#jpPlay")                    # 续播
    page.wait_for_timeout(1200)
    resumed = page.evaluate("() => S.jpActive")
    page.evaluate("() => stopMelody()")

    idx = [a for a, _ in seq if a >= 0]
    check("播放中光标单调向前（不倒退）", all(b >= a for a, b in zip(idx, idx[1:])), repr(idx))
    check("同一时刻最多一个记号被点亮", all(n <= 1 for _, n in seq), repr(seq))
    check("播放确实在推进光标", len(set(idx)) >= 2, repr(idx))
    check("暂停时记住了续播位置", off > 0.2, f"melodyOffset={off}")
    check("暂停后续播从原位置继续（不跳回）", resumed >= mid, f"{mid} -> {resumed}")
    scrolled = [t for t in tops if t["scrollable"]]
    check("确实发生了纵向滚动", any(t["scrollTop"] > 0 for t in scrolled), repr(scrolled[:3]))
    check("光标始终不超过中间行",
          bool(scrolled) and all(t["top"] <= t["mid"] + 4 for t in scrolled),
          repr([(round(t["top"]), round(t["mid"])) for t in scrolled if t["top"] > t["mid"]+4][:5]))
    page.evaluate("() => { document.querySelector('#jpSheet').style.maxHeight=''; }")

    # ---- 1e) 谱面必须静态：高亮切换不能让任何记号位移（补偿滚动后比内容坐标） ----
    def token_boxes():
        return page.evaluate(
            "() => { const box=document.querySelector('#jpSheet');"
            "const br=box.getBoundingClientRect();"
            "return [...box.querySelectorAll('.jp-tok')].map(e => {"
            "  const r=e.getBoundingClientRect();"
            "  return [Math.round((r.left-br.left+box.scrollLeft)*10)/10,"
            "          Math.round((r.top-br.top+box.scrollTop)*10)/10,"
            "          Math.round(r.width*10)/10]; }); }"
        )
    page.evaluate("() => { seekToSeconds(0); highlightAt(0.2); }")
    base_boxes = token_boxes()
    for t in (0.8, 1.6, 2.4, 3.2, 4.0, 5.2, 6.4, 7.2):
        page.evaluate(f"() => highlightAt({t})")
    moved = [(i, a, b) for i, (a, b) in enumerate(zip(base_boxes, token_boxes())) if a != b]
    check("高亮移动时谱面完全不动（布局是静态的）", not moved,
          f"{len(moved)} 个记号发生位移，例：{moved[:3]}")

    # ---- 1f) 密集小节：记号不能越出小节线，也不能相互重叠 ----
    overflow = page.evaluate(
        "() => { const out=[];"
        "for (const cell of document.querySelectorAll('.jp-cell')) {"
        "  const cr=cell.getBoundingClientRect();"
        "  const ts=[...cell.querySelectorAll('.jp-tok')].map(e=>e.getBoundingClientRect());"
        "  ts.forEach((r,i)=>{"
        "    if (r.left < cr.left-1 || r.right > cr.right+1)"
        "      out.push(['out', i, Math.round(r.left-cr.left), Math.round(r.right-cr.right)]);"
        "    if (i && r.left < ts[i-1].right-0.5) out.push(['overlap', i]);"
        "  }); }"
        " return out; }"
    )
    check("密集小节内记号不越界、不相互重叠", not overflow, repr(overflow[:6]))

    if os.environ.get("SMOKE_SHOT"):
        page.evaluate("() => { const s=document.querySelector('#jpSheet'); s.scrollLeft=0; s.scrollTop=0;"
                      " highlightAt(0.2); }")
        # 底部状态栏是 position:fixed，会把面板底部的播放条盖住（页面本身如此），
        # 截图前先藏掉，只为看清版式；不影响任何断言。
        page.evaluate("() => { const s=document.querySelector('.statusbar'); if(s) s.style.display='none'; }")
        page.locator("#jpPanel").screenshot(path=os.environ["SMOKE_SHOT"])
        page.screenshot(path=os.environ["SMOKE_SHOT"] + ".full.png", full_page=True)

    # ---- 2) 旧 pianoroll.js 兜底 ----
    page.evaluate("() => { for (const m of ['getMeasures','activeTrackIndex','secToPos']) delete roll[m]; }")
    page.evaluate("() => { document.querySelector('#jpPanel').hidden = true; }")
    before = len(errors)
    page.click("#jpExport")
    page.wait_for_selector("#jpPanel:not([hidden])", timeout=8000)
    sheet2 = page.inner_text("#jpSheet")
    check("旧脚本下仍能出谱（降级，按 BPM 估算节奏）", any(ch in sheet2 for ch in "1234567"), repr(sheet2[:80]))
    check("旧脚本下不抛未捕获异常", len(errors) == before, "; ".join(errors[before:]))

    browser.close()

print()
if FAILS:
    print(f"失败 {len(FAILS)} 项：" + "、".join(FAILS))
    raise SystemExit(1)
print("全部通过")
