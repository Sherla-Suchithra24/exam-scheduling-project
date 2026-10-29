#!/usr/bin/env python3
"""Generate the same dataset twice and compare CSV row counts and SHA-256 hashes."""
import argparse, hashlib, tempfile
from pathlib import Path
from generate_data import generate

def manifest(path):
    result={}
    for p in sorted(Path(path).glob("*.csv")):
        b=p.read_bytes()
        result[p.name]={"rows":sum(1 for _ in p.open(encoding="utf-8"))-1,"sha256":hashlib.sha256(b).hexdigest()}
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scale",choices=["starter","full"],default="starter")
    p.add_argument("--seed",type=int,default=20261022)
    a=p.parse_args()
    with tempfile.TemporaryDirectory() as x, tempfile.TemporaryDirectory() as y:
        generate(a.scale,a.seed,x); generate(a.scale,a.seed,y)
        m1,m2=manifest(x),manifest(y)
        ok=m1==m2
        print({"scale":a.scale,"seed":a.seed,"reproducible":ok,"files_checked":len(m1),"files":m1})
        if not ok: raise SystemExit(1)
if __name__=="__main__":main()
