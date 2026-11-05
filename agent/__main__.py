"""Video agent — console version (the Telegram bot will call the same functions).

  python3 -m agent ingest  <proj> <file|drive-url> [more sources…]   analyse raw footage
  python3 -m agent plan    <proj> --template stylist_story -n 3      Claude writes main cut + variants → plans.md
  python3 -m agent plan    <proj> --feedback "в v2 хук короче"         revise the plans with your notes
  python3 -m agent review  <proj>                                     print the plans for approval
  python3 -m agent render  <proj> [--only main,v1] [--stills 2,10]   approved plans → out/agent_<proj>_<id>_*.mp4
  python3 -m agent templates                                          list templates

Plans live in work/agent/<proj>/plans.json — they can also be edited by hand before render.
"""
import argparse, json, subprocess, sys

from .config import ROOT, TEMPLATES, proj_dirs


def main():
    ap = argparse.ArgumentParser(prog="agent", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ingest")
    a.add_argument("proj")
    a.add_argument("inputs", nargs="+")
    a.add_argument("--lang", default="ru")
    a.add_argument("--prompt", help="hint for speech recognition: names, brands, places")
    a = sub.add_parser("plan")
    a.add_argument("proj")
    a.add_argument("--template")
    a.add_argument("-n", "--variants", type=int, default=3)
    a.add_argument("--feedback")
    a.add_argument("--no-check", action="store_true")
    a = sub.add_parser("review")
    a.add_argument("proj")
    a = sub.add_parser("render")
    a.add_argument("proj")
    a.add_argument("--only", help="comma-separated plan ids")
    a.add_argument("--stills", help="comma-separated frame numbers: stills only")
    sub.add_parser("templates")
    args = ap.parse_args()

    if args.cmd == "templates":
        import yaml

        for p in sorted(TEMPLATES.glob("*.yaml")):
            print(f"{p.stem:20s} {yaml.safe_load(p.read_text()).get('description', '')}")
        return

    work, _ = proj_dirs(args.proj)
    pj_path = work / "project.json"

    if args.cmd == "ingest":
        from .ingest import ingest

        ingest(args.proj, args.inputs, args.lang, args.prompt)
        return

    pj = json.load(open(pj_path))
    if args.cmd == "plan":
        from . import brain

        pj["template"] = args.template or pj.get("template") or "stylist_story"
        json.dump(pj, open(pj_path, "w"), ensure_ascii=False, indent=1)
        ps = brain.plan(args.proj, pj["template"], args.variants, args.feedback)
        print(brain.review(ps))
        if not args.no_check:
            rep = brain.check(args.proj, ps)
            (work / "check.json").write_text(rep.model_dump_json(indent=1))
            for c in rep.checks:
                print(f"meaning {c.plan_id}: {'OK' if c.ok else 'ПРОБЛЕМЫ'}" + "".join(f"\n  - {p}" for p in c.problems))
        print(f"\nплан: {work / 'plans.md'}")
    elif args.cmd == "review":
        print((work / "plans.md").read_text())
    elif args.cmd == "render":
        from . import brain
        from .build import build

        ps = brain.load(args.proj)
        only = set(args.only.split(",")) if args.only else None
        for p in ps.plans:
            if only and p.id not in only:
                continue
            build(args.proj, p, pj.get("template", "stylist_story"))
            name = f"agent_{args.proj}_{p.id}"
            cmd = [sys.executable, str(ROOT / "scripts" / "reel" / "render.py"), name]
            if args.stills:
                cmd += ["--stills", args.stills]
            subprocess.run(cmd, check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
