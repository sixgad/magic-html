# -*- coding: utf-8 -*-
import logging

logging.basicConfig(level=logging.INFO)

import json
import jieba

jieba.setLogLevel(logging.INFO)
from tabulate import tabulate
import numpy as np

from copy import deepcopy
from bs4 import BeautifulSoup
from ltp import StnSplit
from rouge_score.rouge_scorer import _summary_level_lcs

stp = StnSplit()


def get_score(target, prediction):
    def get_sents(text):
        # 分句
        sents = stp.split(text)
        sents = [x for x in sents if len(x)]
        return sents

    target_tokens_list = [
        [x for x in jieba.lcut(s) if x != " "] for s in get_sents(target)
    ]
    prediction_tokens_list = [
        [x for x in jieba.lcut(s) if x != " "] for s in get_sents(prediction)
    ]

    scoress = _summary_level_lcs(target_tokens_list, prediction_tokens_list)
    return scoress


def rouge_eval(ref, cand):
    """
    计算给定的参考文本和候选文本之间的rouge-L的precision，recall and F1 score
    :param ref: str, reference_txt， 即true label
    :param cand: str, candidate_text， 即pred label
    :return: 列表，元素是字典
    """
    t = {"prec": 1, "rec": 1, "f1": 1}
    if ref == cand:
        return t
    score = get_score(ref, cand)
    t["prec"] = score.precision
    t["rec"] = score.recall
    t["f1"] = score.fmeasure
    return t


def evaluate_result(datas):
    scores = []
    prec = []
    rec = []
    for x in datas:
        scores.append(rouge_eval(x["content"], x["extract_content"]))
    for item in scores:
        prec.append(item["prec"])
        rec.append(item["rec"])

    prec_mean = np.array(prec).mean()
    rec_mean = np.array(rec).mean()
    f1_mean = 2 * prec_mean * rec_mean / (prec_mean + rec_mean)
    global_info["prec_mean"].append(prec_mean)
    global_info["rec_mean"].append(rec_mean)
    global_info["f1_mean"].append(f1_mean)


def get_content_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # 使用get_text()方法抽取所有文本内容，参数"\n"作为不同标签间的分隔符，strip=True去除多余空白
    text_content = soup.get_text("\n", strip=True)
    return text_content


global_datas = []

global_info = {
    "func": [],
    "prec_mean": [],
    "rec_mean": [],
    "f1_mean": [],
}

with open("data/forum/base.json", "r", encoding="utf-8") as f:
    for k, v in json.loads(f.read()).items():
        html_str = ""
        with open(f"data/forum/htmls/{k}.html", "r", encoding="utf-8") as ff:
            html_str = ff.read()
            v["html"] = html_str
        global_datas.append(v)


def run_magic_html(name):
    from magic_html import GeneralExtractor

    datas = deepcopy(global_datas)
    extractor = GeneralExtractor()
    for x in datas:
        x["extract_content"] = get_content_text(
            extractor.extract(html=x["html"], base_url=x["url"], html_type="forum")[
                "html"
            ]
        )
    global_info["func"].append(name)
    evaluate_result(datas)


def run_trafilatura(name):
    from trafilatura import extract

    datas = deepcopy(global_datas)
    for x in datas:
        x["extract_content"] = extract(
            x["html"], include_comments=True, no_fallback=True
        )
    global_info["func"].append(name)
    evaluate_result(datas)


def run_trafilatura_fallback(name):
    from trafilatura import extract

    datas = deepcopy(global_datas)
    for x in datas:
        x["extract_content"] = extract(
            x["html"], include_comments=True, no_fallback=False
        )
    global_info["func"].append(name)
    evaluate_result(datas)


def run_readability_lxml(name):
    from readability import Document

    datas = deepcopy(global_datas)
    for x in datas:
        x["extract_content"] = get_content_text(Document(x["html"]).summary())
    global_info["func"].append(name)
    evaluate_result(datas)


def run_newspaper3k(name):
    from newspaper import fulltext

    datas = deepcopy(global_datas)
    for x in datas:
        try:
            x["extract_content"] = fulltext(x["html"])
        except:
            x["extract_content"] = ""
    global_info["func"].append(name)
    evaluate_result(datas)


def run_goose3(name):
    from goose3 import Goose

    g = Goose()
    datas = deepcopy(global_datas)
    for x in datas:
        x["extract_content"] = g.extract(raw_html=x["html"]).cleaned_text
    global_info["func"].append(name)
    evaluate_result(datas)


def run_justext(name):
    import justext

    datas = deepcopy(global_datas)
    for x in datas:
        paragraphs = justext.justext(x["html"], justext.get_stoplist("German"), 50, 200, 0.1, 0.2, 0.2, 200,
                                     True)  # stop_words
        valid = [
            paragraph.text
            for paragraph in paragraphs
            if not paragraph.is_boilerplate
        ]

        x["extract_content"] = ' '.join(valid)
    global_info["func"].append(name)
    evaluate_result(datas)


def run_gne(name):
    from gne import GeneralNewsExtractor

    extractor = GeneralNewsExtractor()
    datas = deepcopy(global_datas)
    for x in datas:
        x["extract_content"] = extractor.extract(x["html"])["content"]
    global_info["func"].append(name)
    evaluate_result(datas)


# 自定义需要对比的方法
all_funcs = {
    "magic_html": run_magic_html,
    "trafilatura": run_trafilatura,
    "trafilatura_fallback": run_trafilatura_fallback,
    "readability-lxml": run_readability_lxml,
    "newspaper3k": run_newspaper3k,
    "goose3": run_goose3,
    "justext": run_justext,
    "gne": run_gne
}

for k, v in all_funcs.items():
    v(k)

print("论坛类型网页")
print("当前结果")
print(tabulate(global_info, headers="keys", tablefmt="fancy_grid"))
print("基准结果")
print('''
╒══════════════════════╤═════════════╤════════════╤═══════════╕
│ func                 │   prec_mean │   rec_mean │   f1_mean │
╞══════════════════════╪═════════════╪════════════╪═══════════╡
│ magic_html           │    0.752323 │   0.964762 │  0.845401 │
├──────────────────────┼─────────────┼────────────┼───────────┤
│ trafilatura          │    0.711983 │   0.568848 │  0.632418 │
├──────────────────────┼─────────────┼────────────┼───────────┤
│ trafilatura_fallback │    0.781724 │   0.557774 │  0.651028 │
├──────────────────────┼─────────────┼────────────┼───────────┤
│ readability-lxml     │    0.55441  │   0.228667 │  0.323788 │
├──────────────────────┼─────────────┼────────────┼───────────┤
│ newspaper3k          │    0.716421 │   0.19569  │  0.307411 │
├──────────────────────┼─────────────┼────────────┼───────────┤
│ goose3               │    0.551646 │   0.147048 │  0.2322   │
├──────────────────────┼─────────────┼────────────┼───────────┤
│ justext              │    0.542019 │   0.204443 │  0.296899 │
├──────────────────────┼─────────────┼────────────┼───────────┤
│ gne                  │    0.846939 │   0.125834 │  0.219114 │
╘══════════════════════╧═════════════╧════════════╧═══════════╛
'''.strip())