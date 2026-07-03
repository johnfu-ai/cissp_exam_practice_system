"""ETL CLI. Run as `python -m app.etl.cli <command>`.

Commands:
  preview <slug>        dry-run a dataset, print summary
  commit <run_id>       commit a previewed run
  rollback <run_id>     discard a previewed run
  run <slug>            preview + commit in one step
"""

import argparse
import sys
import uuid

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.etl.runner import run_commit, run_preview, run_rollback
from app.models.auth import Organization
from app.models.etl import EtlDataset


def _session():
    return get_sessionmaker()()


def _org_id(session):
    org = session.execute(select(Organization).filter_by(slug="personal")).scalar_one_or_none()
    if org is None:
        org = session.execute(select(Organization).limit(1)).scalar_one()
    return org.id


def _dataset(session, slug):
    ds = session.execute(select(EtlDataset).filter_by(slug=slug)).scalar_one_or_none()
    if ds is None:
        print(f"dataset '{slug}' not found", file=sys.stderr)
        sys.exit(1)
    return ds


def _print_summary(run):
    s = run.preview_summary or {}
    print(f"run_id: {run.id}")
    print(f"phase:  {run.phase.value}")
    print(f"would_create: {s.get('would_create')}")
    print(f"would_update: {s.get('would_update')}")
    print(f"unchanged:    {s.get('unchanged')}")
    print(f"by_type:      {s.get('by_type')}")
    print(f"by_language:  {s.get('by_language')}")
    errs = s.get("errors") or []
    print(f"errors:       {len(errs)}")
    for e in errs[:10]:
        print(f"  - {e}")


def cmd_preview(args):
    session = _session()
    try:
        run = run_preview(session, _org_id(session), _dataset(session, args.slug))
        session.commit()
        _print_summary(run)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cmd_commit(args):
    session = _session()
    try:
        run = run_commit(session, _org_id(session), uuid.UUID(args.run_id))
        session.commit()
        print(f"committed run {run.id}, phase={run.phase.value}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cmd_rollback(args):
    session = _session()
    try:
        run = run_rollback(session, uuid.UUID(args.run_id), org_id=_org_id(session))
        session.commit()
        print(f"rolled back run {run.id}, phase={run.phase.value}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cmd_run(args):
    session = _session()
    try:
        run = run_preview(session, _org_id(session), _dataset(session, args.slug))
        session.commit()
        _print_summary(run)
        run = run_commit(session, _org_id(session), run.id)
        session.commit()
        print(f"committed run {run.id}, phase={run.phase.value}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="app.etl.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preview"); p.add_argument("slug"); p.set_defaults(func=cmd_preview)
    c = sub.add_parser("commit"); c.add_argument("run_id"); c.set_defaults(func=cmd_commit)
    r = sub.add_parser("rollback"); r.add_argument("run_id"); r.set_defaults(func=cmd_rollback)
    rn = sub.add_parser("run"); rn.add_argument("slug"); rn.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
