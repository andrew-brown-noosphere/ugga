"""
CLI entry point for UGA Course Scheduler.

Commands:
- import: Import a PDF schedule
- serve: Start the API server
- stats: Show schedule statistics
"""
import argparse
import os
import sys
from pathlib import Path


def import_pdf(args):
    """Import a PDF schedule into the database."""
    from src.services.course_service import create_service

    os.makedirs("data", exist_ok=True)
    service = create_service()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

    print(f"Importing {pdf_path}...")
    schedule, result = service.import_pdf(pdf_path, args.url or "")

    print(f"\n=== Import Complete ===")
    print(f"Schedule ID: {schedule.id}")
    print(f"Term: {schedule.term}")
    print(f"Courses: {schedule.total_courses}")
    print(f"Sections: {schedule.total_sections}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Errors: {len(result.errors)}")

    if args.verbose and result.warnings:
        print(f"\n=== Warnings ===")
        for w in result.warnings[:20]:
            print(f"  - {w}")
        if len(result.warnings) > 20:
            print(f"  ... and {len(result.warnings) - 20} more")


def serve(args):
    """Start the API server."""
    import uvicorn

    os.makedirs("data", exist_ok=True)

    print(f"Starting UGA Course Scheduler API on http://{args.host}:{args.port}")
    print(f"API docs available at http://{args.host}:{args.port}/docs")

    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def stats(args):
    """Show schedule statistics."""
    from src.services.course_service import create_service

    service = create_service()
    schedule = service.get_current_schedule()

    if not schedule:
        print("No schedule found. Import a PDF first.")
        sys.exit(1)

    stats_data = service.get_stats()

    print(f"\n=== {stats_data['term']} Statistics ===")
    print(f"Total Courses:      {stats_data['total_courses']:,}")
    print(f"Total Sections:     {stats_data['total_sections']:,}")
    print(f"Available Sections: {stats_data['available_sections']:,}")
    print(f"Total Seats:        {stats_data['total_seats']:,}")
    print(f"Available Seats:    {stats_data['available_seats']:,}")
    print(f"Instructors:        {stats_data['instructor_count']:,}")
    print(f"Last Updated:       {stats_data['parse_date']}")


def search(args):
    """Search for courses."""
    from src.services.course_service import create_service

    service = create_service()
    courses = service.get_courses(
        search=args.query,
        subject=args.subject,
        instructor=args.instructor,
        has_availability=args.available,
        limit=args.limit,
    )

    if not courses:
        print("No courses found matching your criteria.")
        return

    print(f"\n=== Found {len(courses)} courses ===\n")
    for c in courses:
        avail = "✓" if c.has_availability else "✗"
        print(f"[{avail}] {c.course_code}: {c.title}")
        print(f"    Department: {c.department}")
        print(f"    Sections: {len(c.sections)}, "
              f"Seats: {c.available_seats}/{c.total_seats}")
        if args.verbose:
            for s in c.sections:
                status = "🟢" if s.is_available else "🔴"
                print(f"      {status} CRN {s.crn}: {s.instructor or 'TBD'}, "
                      f"{s.seats_available}/{s.class_size} seats")
        print()


def bulletin_scrape(args):
    """Scrape program or course from UGA Bulletin."""
    from src.services.bulletin_firecrawl import BulletinFirecrawlScraper
    import json

    try:
        scraper = BulletinFirecrawlScraper(skip_db=not args.save)
    except ValueError as e:
        print(f"Error: {e}")
        print("Set FIRECRAWL_API_KEY in your .env file")
        sys.exit(1)

    if args.program:
        # Parse program ID - can be "73962" or "73962:ARTS"
        parts = args.program.split(":")
        bulletin_id = parts[0]
        college_code = parts[1] if len(parts) > 1 else "ARTS"

        print(f"Scraping program {bulletin_id} (college: {college_code})...")
        program = scraper.scrape_program(bulletin_id, college_code)

        if program:
            print(f"\n=== {program.name} ({program.degree_type}) ===")
            print(f"Department: {program.department or 'N/A'}")
            print(f"Total Hours: {program.total_hours or 'N/A'}")
            print(f"College: {program.college_code}")
            print(f"URL: {program.bulletin_url}")

            if program.overview:
                print(f"\nOverview: {program.overview[:300]}...")

            print(f"\nRequirements ({len(program.requirements)}):")
            for req in program.requirements:
                print(f"  - {req.name} ({req.required_hours or '?'} hrs)")
                print(f"    Category: {req.category}")
                print(f"    Courses: {len(req.courses)}")
                for course in req.courses[:5]:
                    print(f"      * {course.course_code}: {course.title or 'N/A'}")
                if len(req.courses) > 5:
                    print(f"      ... and {len(req.courses) - 5} more")

            if args.save:
                scraper.save_program(program)
                print(f"\nSaved to database!")

            if args.json:
                from dataclasses import asdict
                print(f"\n=== JSON ===")
                print(json.dumps(asdict(program), indent=2, default=str))
        else:
            print("Failed to scrape program")
            sys.exit(1)

    elif args.course:
        print(f"Scraping course {args.course}...")
        course = scraper.scrape_course(args.course)

        if course:
            print(f"\n=== {course.course_code}: {course.title} ===")
            print(f"Credits: {course.credit_hours or 'N/A'}")
            print(f"URL: {course.bulletin_url}")

            if course.description:
                print(f"\nDescription: {course.description[:500]}...")

            if course.prerequisites:
                print(f"\nPrerequisites: {course.prerequisites}")

            if course.semester_offered:
                print(f"Offered: {course.semester_offered}")

            if args.save:
                scraper.save_course(course)
                print(f"\nSaved to database!")

            if args.json:
                from dataclasses import asdict
                print(f"\n=== JSON ===")
                print(json.dumps(asdict(course), indent=2, default=str))
        else:
            print("Failed to scrape course")
            sys.exit(1)

    else:
        print("Specify --program or --course to scrape")
        sys.exit(1)


def bulletin_list(args):
    """List programs from the bulletin (uses Playwright)."""
    import asyncio

    async def _list():
        from src.services.bulletin_scraper import BulletinScraper

        async with BulletinScraper(skip_db=True) as scraper:
            print(f"Searching for programs...")
            programs = await scraper.search_programs(
                keyword=args.keyword or "",
                program_types=args.types.split(",") if args.types else ["UG"],
            )

            print(f"\n=== Found {len(programs)} programs ===\n")
            for name, bid, college in programs[:args.limit]:
                print(f"  {name}: {bid}:{college}")

            if len(programs) > args.limit:
                print(f"\n  ... and {len(programs) - args.limit} more (use --limit to show more)")

    asyncio.run(_list())


def course_info(args):
    """Get detailed course information."""
    import json
    from src.services.course_linker import CourseLinker

    linker = CourseLinker()
    code = args.code.upper()

    info = linker.get_course_info(code)
    if not info:
        print(f"Course {code} not found")
        sys.exit(1)

    print(f"\n=== {info.code}: {info.title} ===")
    print(f"Credits: {info.credit_hours or 'N/A'}")

    if info.description:
        print(f"\nDescription: {info.description[:300]}...")

    if info.prerequisites_text:
        print(f"\nPrerequisites (text): {info.prerequisites_text}")

    if info.prerequisites_structured:
        print(f"\nPrerequisites (structured):")
        for req in info.prerequisites_structured:
            if req.get("logic") == "OR":
                options = [o["code"] for o in req["options"]]
                print(f"  - One of: {', '.join(options)}")
            else:
                print(f"  - {req.get('course', {}).get('code', 'Unknown')}")

    if info.sections_available > 0:
        print(f"\nThis semester:")
        print(f"  Sections: {info.sections_available}")
        print(f"  Seats: {info.available_seats}/{info.total_seats}")
        if info.instructors:
            print(f"  Instructors: {', '.join(info.instructors[:5])}")

    if args.prereqs:
        print(f"\n=== Prerequisite Chain ===")
        chain = linker.get_prerequisite_chain(code)
        _print_prereq_tree(chain, indent=0)

    if args.unlocks:
        print(f"\n=== Courses Unlocked ===")
        unlocks = linker.get_unlocked_courses(code)
        for u in unlocks[:20]:
            status = "Ready" if u["fully_unlocked"] else f"{u['remaining_prereqs']} more prereq(s)"
            print(f"  {u['code']}: {status}")


def _print_prereq_tree(node, indent=0):
    """Print prerequisite tree recursively."""
    prefix = "  " * indent
    if isinstance(node, dict):
        if "course" in node:
            print(f"{prefix}- {node['course']}")
            for prereq in node.get("prerequisites", []):
                _print_prereq_tree(prereq, indent + 1)
        elif node.get("type") == "OR":
            print(f"{prefix}- ONE OF:")
            for opt in node.get("options", []):
                _print_prereq_tree(opt, indent + 1)


def link_courses(args):
    """Link schedule courses to bulletin courses."""
    from src.services.course_linker import CourseLinker

    print("Linking schedule courses to bulletin...")
    linker = CourseLinker()
    stats = linker.link_schedule_to_bulletin()

    print(f"\n=== Link Complete ===")
    print(f"Courses processed: {stats['courses_processed']}")
    print(f"Exact matches: {stats['exact_matches']}")
    print(f"No match: {stats['no_match']}")


def parse_prerequisites(args):
    """Parse prerequisites from all bulletin courses."""
    from src.services.prerequisite_parser import PrerequisiteParser

    print("Parsing prerequisites from bulletin courses...")
    parser = PrerequisiteParser()
    stats = parser.process_all_bulletin_courses()

    print(f"\n=== Parse Complete ===")
    print(f"Courses processed: {stats['courses_processed']}")
    print(f"Prerequisites created: {stats['prerequisites_created']}")
    print(f"Equivalents created: {stats['equivalents_created']}")
    print(f"Errors: {stats['errors']}")


def scrape_all_programs(args):
    """Scrape all programs from the programs list file."""
    import asyncio
    from pathlib import Path

    async def _scrape():
        from src.services.bulletin_scraper import BulletinScraper

        # Read programs list
        programs_file = Path("data/programs_list.txt")
        if not programs_file.exists():
            print(f"Error: {programs_file} not found")
            sys.exit(1)

        programs_to_scrape = []
        with open(programs_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Format: TYPE|DEGREE|BULLETIN_ID|COLLEGE_CODE
                parts = line.split("|")
                if len(parts) >= 4:
                    prog_type, degree, bulletin_id, college_code = parts[:4]
                    # Filter by type if specified
                    if args.types and prog_type not in args.types.split(","):
                        continue
                    programs_to_scrape.append((bulletin_id, college_code, prog_type, degree))

        print(f"Found {len(programs_to_scrape)} programs to scrape")

        if args.limit:
            programs_to_scrape = programs_to_scrape[:args.limit]
            print(f"Limited to {args.limit} programs")

        async with BulletinScraper(skip_db=not args.save) as scraper:
            success = 0
            failed = 0

            for i, (bulletin_id, college_code, prog_type, degree) in enumerate(programs_to_scrape):
                print(f"\n[{i+1}/{len(programs_to_scrape)}] Scraping {prog_type} {degree} ({bulletin_id}:{college_code})...")

                try:
                    program = await scraper.scrape_program(bulletin_id, college_code)

                    if program:
                        print(f"  -> {program.name}: {len(program.requirements)} requirements")
                        if args.save:
                            scraper.save_program(program)
                            print(f"  -> Saved to database")
                        success += 1
                    else:
                        print(f"  -> Failed to scrape")
                        failed += 1

                except Exception as e:
                    print(f"  -> Error: {e}")
                    failed += 1

                # Be nice to the server
                await asyncio.sleep(1)

            print(f"\n=== Complete ===")
            print(f"Success: {success}")
            print(f"Failed: {failed}")

    asyncio.run(_scrape())


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="UGA Course Scheduler - Smart course planning for UGA students",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import a PDF schedule")
    import_parser.add_argument("pdf", help="Path to PDF file")
    import_parser.add_argument("--url", help="Source URL for the PDF")
    import_parser.add_argument("-v", "--verbose", action="store_true", help="Show warnings")
    import_parser.set_defaults(func=import_pdf)

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve_parser.set_defaults(func=serve)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show schedule statistics")
    stats_parser.set_defaults(func=stats)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for courses")
    search_parser.add_argument("query", nargs="?", help="Search query")
    search_parser.add_argument("-s", "--subject", help="Filter by subject code")
    search_parser.add_argument("-i", "--instructor", help="Filter by instructor")
    search_parser.add_argument("-a", "--available", action="store_true",
                               help="Only show available courses")
    search_parser.add_argument("-l", "--limit", type=int, default=20, help="Max results")
    search_parser.add_argument("-v", "--verbose", action="store_true", help="Show section details")
    search_parser.set_defaults(func=search)

    # Bulletin scrape command
    bulletin_parser = subparsers.add_parser("bulletin", help="Scrape UGA Bulletin")
    bulletin_parser.add_argument("-p", "--program", help="Program ID (e.g., 73962 or 73962:ARTS)")
    bulletin_parser.add_argument("-c", "--course", help="Course bulletin ID (e.g., 20694)")
    bulletin_parser.add_argument("--save", action="store_true", help="Save to database")
    bulletin_parser.add_argument("--json", action="store_true", help="Output as JSON")
    bulletin_parser.set_defaults(func=bulletin_scrape)

    # Bulletin list command
    list_parser = subparsers.add_parser("bulletin-list", help="List programs from UGA Bulletin")
    list_parser.add_argument("-k", "--keyword", help="Search keyword")
    list_parser.add_argument("-t", "--types", default="UG",
                            help="Program types (comma-separated: UG,GM,MINOR,CERT-UG,CERT-GM)")
    list_parser.add_argument("-l", "--limit", type=int, default=50, help="Max results to show")
    list_parser.set_defaults(func=bulletin_list)

    # Course info command
    course_parser = subparsers.add_parser("course", help="Get detailed course information")
    course_parser.add_argument("code", help="Course code (e.g., CSCI 1301)")
    course_parser.add_argument("--prereqs", action="store_true", help="Show prerequisite chain")
    course_parser.add_argument("--unlocks", action="store_true", help="Show courses this unlocks")
    course_parser.set_defaults(func=course_info)

    # Link courses command
    link_parser = subparsers.add_parser("link", help="Link schedule courses to bulletin")
    link_parser.set_defaults(func=link_courses)

    # Parse prerequisites command
    parse_parser = subparsers.add_parser("parse-prereqs", help="Parse prerequisites from bulletin courses")
    parse_parser.set_defaults(func=parse_prerequisites)

    # Scrape all programs command
    scrape_all_parser = subparsers.add_parser("scrape-programs", help="Scrape all programs from programs_list.txt")
    scrape_all_parser.add_argument("-t", "--types", help="Filter by program types (e.g., UG,GM,MINOR)")
    scrape_all_parser.add_argument("-l", "--limit", type=int, help="Limit number of programs to scrape")
    scrape_all_parser.add_argument("--save", action="store_true", help="Save to database")
    scrape_all_parser.set_defaults(func=scrape_all_programs)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
