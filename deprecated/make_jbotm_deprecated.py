# -*- coding: utf-8 -*-

import sys, json, zipfile, datetime
from jbovlaste_xmltojson import make_dict_from_xml, save_json
from collections import OrderedDict as Odict
from ponjo_tweak import goodnotes, sortcontents, integrate_gloss, delete_emptynotes, \
                        delete_dollar, add_relations, add_relations_for_multi
import otmjson as otm

lang_list = ["en", "ja", "jbo", "eo", "en-simple", "de", "fr", "ru", "zh", "es"]
special_lang_list = ["top3", "top5", "all"]

def make_content (valsi, opt, title):
    if not isinstance(valsi[opt], list):
        optlist = [valsi[opt]]
    else:
        optlist = valsi[opt]
    options = []
    if opt == "rafsi":
        options = optlist
        return otm.content(title, "   ".join(options))
    else:
        for _od in optlist:
            word = _od["@word"]
            if "@sense" in _od.keys():
                word += "; {}".format(_od["@sense"])
            if opt == "keyword":
                word = "[{}]: {}".format(_od["@place"], word)
            options.append(word)
    return otm.content(title, ", ".join(options))

def make_contents(valsi):
    contents = []
    if "notes" in valsi.keys():
        contents.append(otm.content("notes", valsi["notes"]))
    for option in [("glossword", "gloss"), ("keyword", "keyword"), ("rafsi", "rafsi")]:
        if option[0] in valsi.keys():
            contents.append(make_content(valsi, *option))
    contents.append(otm.content("username", valsi["user"]["username"]))
    return contents

def make_otmword(valsi):
    try:
        entry = otm.Entry(valsi["@word"], int(valsi["definitionid"]))
    except:
        print(valsi["@word"])
    selmaho = ": " + valsi["selmaho"] if "selmaho" in valsi.keys() else ""
    translation = otm.translation(valsi["@type"]+selmaho, [valsi["definition"]])
    translations = [translation]
    tags = []
    if "@unofficial" in valsi.keys():
        tags.append("unofficial")
    contents = make_contents(valsi)
    variations = []
    relations = []
    return Odict([("entry", entry), ("translations", translations), ("tags", tags),
                    ("contents", contents), ("variations", variations), ("relations", relations)])

def make_otmjson(rawdict, filename, lang, *args):
    _vlaste = []
    for valsi in rawdict:
        _vla = make_otmword(valsi)
        if lang == "ja":
            _vla = delete_emptynotes(sortcontents(integrate_gloss(goodnotes(_vla))))
        if '--nodollar' in args:
            _vla = delete_dollar(_vla)
        _vlaste.append(_vla)
    if '--addrelations' in args:
        from time import time
        import concurrent.futures
        print('add relations...')
        start = time()
        entry_list = [word["entry"] for word in _vlaste]
        letters = ".abcdefgijklmnoprstuvwxyz"
        letters += letters[1:].upper()
        entry_dict = {letter: [e for e in entry_list if e["form"][0] == letter] for letter in letters}
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=8)
        max_n = len(_vlaste)
        split_n = 8
        list_size = max_n // split_n
        tasks_list = [_vlaste[x:x + list_size] for x in range(0, max_n, list_size)]
        futures = [executor.submit(add_relations_for_multi, tasks, entry_dict) for tasks in tasks_list]
        done_task = 0
        new_vlaste = []
        for future in concurrent.futures.as_completed(futures):
            done_task += len(future.result())
            new_vlaste.extend(future.result())
            sys.stdout.write("\r{}/{} words done.".format(done_task, max_n))
            sys.stdout.flush()
        end = time()
        print(" ({:.1f} sec.)".format(end-start))
        _vlaste = new_vlaste

    _langdata = {"from":"jbo", "to": lang}
    _date = str(datetime.date.today())
    _j = Odict([("words", _vlaste), ("zpdic", {"alphabetOrder":".'aAbBcCdDeEfFgGiIjJkKlLmMnNoOpPrRsStTuUvVxXyYzZ"}),
                ("meta", {"lang": _langdata, "generated_date": _date})])

    otmjson = json.dumps(_j, indent=2, ensure_ascii=False)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(otmjson)
        print("Written to {}.".format(filename))

# ------------------------------------------------------------------------

def parse_arg():
    if len(sys.argv) == 1 :
        raise RuntimeError("No command line variables. Specify a language.")
    if len(sys.argv) >= 3:
        command = sys.argv[2:]
    else:
        command = []
    langs = sys.argv[1].split('/')
    if all(lang in lang_list or lang in special_lang_list for lang in langs):
        return langs, command
    else:
        raise RuntimeError("Invalid. Available: {}".format(", ".join(lang_list)))

def load_rawdict(lang):
    filename = 'json/jbo-{}.json'.format(lang)
    try:
        with open(filename, encoding='utf-8') as f:
            rawdict = json.loads(f.read())
        print("Loaded {}".format(filename))
    except:
        print("Couldn't find '{}'. Generated by xmltojson...".format(filename))
        rawdict, _ = make_dict_from_xml(lang)
        print("OK, loaded.")
        save_json(rawdict, lang)
    return rawdict

def router(langs, *args):
    filename_temp = 'otm-json/jbo-{}_otm.json'
    if 'all' in langs:
        running = lang_list
    elif 'top5' in langs:
        if len(lang_list) >= 5:
            running = lang_list[:5] + [lang for lang in langs if lang not in special_lang_list]
        else:
            running = lang_list
    elif 'top3' in langs:
        if len(lang_list) >= 3:
            running = lang_list[:3] + [lang for lang in langs if lang not in special_lang_list]
        else:
            running = lang_list
    else:
        running = langs
    print("Generating {} dictionary...".format(", ".join(running)))
    for lang in running:
        make_otmjson(load_rawdict(lang), filename_temp.format(lang), lang, *args)
    return running

def zip_otms(langs):
    filename_temp = 'otm-json/jbo-{}_otm.json'
    if 'all' in langs:
        langs = lang_list[1:]
    zip_path = 'zip/{}-otmjson.zip'.format("-".join(langs))
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for lang in langs:
            zf.write(filename_temp.format(lang))

if __name__ == '__main__':
    langs, command = parse_arg()
    pure_langs = router(langs, *command)
    if '--zip' in command:
        print("zip...")
        zip_otms(pure_langs)
    print("Success!")