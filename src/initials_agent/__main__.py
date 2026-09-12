import argparse
import asyncio
import sys

from .agents.researcher import ResearchAgent
from .config import get_settings
from .logging_config import setup_logging


def main() -> None:
    logger = setup_logging()
    parser = argparse.ArgumentParser(description="Daily Content Agent — sellable multi-brand content product")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # health command
    health_parser = subparsers.add_parser("health", help="Check agent health")
    
    # research command
    research_parser = subparsers.add_parser("research", help="Run daily research")
    research_parser.add_argument("--limit", type=int, default=5, help="Limit number of sources")
    
    # Approval CLI commands
    approval_parser = subparsers.add_parser("approval", help="Manage human approval queue")
    app_subs = approval_parser.add_subparsers(dest="approval_cmd")
    
    app_subs.add_parser("list", help="List pending approvals")
    
    show_p = app_subs.add_parser("show", help="Show approval details")
    show_p.add_argument("id", help="Approval Request ID")
    
    app_p = app_subs.add_parser("approve", help="Approve request")
    app_p.add_argument("id", help="Approval Request ID")
    
    rej_p = app_subs.add_parser("reject", help="Reject request")
    rej_p.add_argument("id", help="Approval Request ID")
    
    regen_p = app_subs.add_parser("regenerate", help="Request regeneration")
    regen_p.add_argument("id", help="Approval Request ID")
    
    # Smoke-test CLI commands
    smoke_parser = subparsers.add_parser("smoke-test", help="Live API smoke tests")
    smoke_subs = smoke_parser.add_subparsers(dest="smoke_cmd")
    smoke_pub = smoke_subs.add_parser("publish", help="Test live publishing (requires env vars)")
    smoke_pub.add_argument("draft_id", help="Draft UUID to publish")
    
    # Image Generation CLI
    image_parser = subparsers.add_parser("image", help="Manage image generation")
    image_subs = image_parser.add_subparsers(dest="image_cmd", required=True)
    
    gen_img_p = image_subs.add_parser("generate", help="Generate an actual AI image from a prompt")
    gen_img_p.add_argument("--prompt", required=True, help="Prompt for the image")
    gen_img_p.add_argument("--width", type=int, default=1080, help="Image width")
    gen_img_p.add_argument("--height", type=int, default=1350, help="Image height")
    gen_img_p.add_argument("--output", default="./output/generated_image.png", help="Output file path")
    
    # Agent Run CLI
    run_parser = subparsers.add_parser("run", help="Run the Daily Content Agent pipeline")
    run_parser.add_argument("--dry-run", action="store_true", help="Execute without modifying real DB or making external API calls")
    run_parser.add_argument("--force", action="store_true", help="Force execution (override safety checks where applicable)")
    run_parser.add_argument("--topic", type=str, default=None, help="Specific topic to research")
    run_parser.add_argument("--no-image", action="store_true", help="Skip visual concept and image generation")
    run_parser.add_argument("--no-publish", action="store_true", help="Skip publishing approved posts")
    
    # Scheduler CLI
    sched_parser = subparsers.add_parser("scheduler", help="Manage the autonomous scheduling daemon")
    sched_subs = sched_parser.add_subparsers(dest="sched_cmd", required=True)
    sched_subs.add_parser("start", help="Start the scheduler daemon")
    sched_subs.add_parser("status", help="View scheduler run statuses")
    sched_subs.add_parser("run-now", help="Force run the pipeline immediately")

    # API server (React SaaS frontend)
    serve_parser = subparsers.add_parser("serve", help="Start the FastAPI server for the web app")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    # Analytics CLI
    analytics_parser = subparsers.add_parser("analytics", help="Manage analytics synchronization and reporting")
    analytics_subs = analytics_parser.add_subparsers(dest="analytics_cmd", required=True)
    analytics_subs.add_parser("sync", help="Poll APIs and store latest analytics snapshots")
    analytics_subs.add_parser("report", help="Generate analytics report and update ContentStrategyProfile")

    args = parser.parse_args()
    
    if args.command == "serve":
        import os
        import uvicorn

        host = os.environ.get("HOST") or args.host
        # Render (and most PaaS) inject PORT; default bind all interfaces in production
        port_env = os.environ.get("PORT")
        port = int(port_env) if port_env else args.port
        if os.environ.get("RENDER") or os.environ.get("APP__ENVIRONMENT", "").lower() == "production":
            host = os.environ.get("HOST") or "0.0.0.0"

        uvicorn.run(
            "initials_agent.api.main:app",
            host=host,
            port=port,
            reload=args.reload,
        )
        sys.exit(0)
    if args.command == "health":
        settings = get_settings()
        logger.info(f"Health check for {settings.app.name} in {settings.app.environment} environment")
        print("OK")
        sys.exit(0)
    elif args.command == "research":
        logger.info(f"Starting research agent (limit={args.limit})")
        agent = ResearchAgent()
        result = asyncio.run(agent.run_daily_research(limit=args.limit))
        logger.info(f"Research complete. Query: {result.query}")
        logger.info(f"Found {len(result.sources)} valid sources.")
        print(result.model_dump_json(indent=2))
        sys.exit(0)
    elif args.command == "smoke-test" and args.smoke_cmd == "publish":
        app_service = ApprovalService()
        req = app_service.get_request(uuid.UUID(args.draft_id))
        if not req:
            print("Approval request not found.")
            asyncio.run(run_smoke())
        
    elif args.command == "approval":
        from initials_agent.db.session import get_engine, get_session_factory
        from initials_agent.repositories.approval import ApprovalRepository
        from initials_agent.services.approval.local import LocalApprovalService
        
        engine = get_engine("sqlite:///initials_agent.db")
        Session = get_session_factory(engine)
        with Session() as session:
            repo = ApprovalRepository(session)
            service = LocalApprovalService(repo)
            
            if args.approval_cmd == "list":
                from initials_agent.db.models import ApprovalRequestModel
                reqs = session.query(ApprovalRequestModel).filter_by(status="pending").all()
                print("--- Pending Approvals ---")
                if not reqs:
                    print("No pending approvals.")
                for r in reqs:
                    print(f"ID: {r.id} | Status: {r.status}")
            elif args.approval_cmd == "approve":
                import uuid
                service.approve(uuid.UUID(args.id))
                session.commit()
                print(f"Approved request {args.id}. It will be published on the next cycle.")
            elif args.approval_cmd == "reject":
                import uuid
                service.reject(uuid.UUID(args.id))
                session.commit()
                print(f"Rejected request {args.id}.")
            
    elif args.command == "image":
        import os
        import io
        from PIL import Image
        from initials_agent.models.content import VisualConcept
        # get_settings is already imported globally at top of __main__
        
        async def run_generate():
            settings = get_settings()
            
            provider_type = settings.image.provider
            if provider_type == "mock":
                print("Error: MockImageProvider is not allowed for this command. Configure a real provider.")
                sys.exit(1)
                
            api_key = settings.image.api_key
            if not api_key or not api_key.get_secret_value():
                print(f"Error: API key for {provider_type} is not configured.")
                sys.exit(1)
                
            if provider_type == "dalle":
                from initials_agent.providers.image.dalle import DalleImageProvider
                provider = DalleImageProvider(api_key.get_secret_value())
            elif provider_type == "gemini":
                from initials_agent.providers.image.gemini import GeminiImageProvider
                provider = GeminiImageProvider(api_key.get_secret_value(), settings.image.model_name)
            elif provider_type == "openrouter":
                from initials_agent.providers.image.openrouter import OpenRouterImageProvider
                provider = OpenRouterImageProvider(api_key.get_secret_value(), settings.image.model_name)
            elif provider_type == "puter":
                from initials_agent.providers.image.puter import PuterImageProvider
                provider = PuterImageProvider(api_key.get_secret_value(), settings.image.model_name)
            else:
                print(f"Error: Unknown provider '{provider_type}'")
                sys.exit(1)
                
            concept = VisualConcept(
                aspect_ratio=f"{args.width}:{args.height}",
                composition="Premium futuristic enterprise technology aesthetic",
                headline="CLI Prompt",
                supporting_text="",
                visual_subject=args.prompt,
                environment="Dark black background",
                lighting="Cinematic lighting",
                color_palette="Electric blue and neon purple",
                typography="Clean modern",
                negative_prompt="No generic humanoid robot",
                brand_requirements="Customer brand identity from Settings",
            )
            
            try:
                print(f"Calling real image provider ({provider_type})...")
                image_bytes = await provider.generate_image(concept)
                
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    img.verify()
                    img = Image.open(io.BytesIO(image_bytes))
                except Exception as e:
                    print(f"Error: Provider returned invalid image data: {e}")
                    sys.exit(1)
                
                fmt = img.format.lower() if img.format else "png"
                if fmt not in ["jpeg", "jpg", "png", "webp"]:
                    print(f"Error: Invalid format returned: {fmt}")
                    sys.exit(1)
                    
                output_path = os.path.abspath(args.output)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                if img.size != (args.width, args.height):
                    img = img.resize((args.width, args.height), Image.Resampling.LANCZOS)
                
                img.save(output_path)
                
                if not os.path.exists(output_path):
                    print("Error: File was not saved successfully.")
                    sys.exit(1)
                    
                print(f"Image generated successfully at: {output_path}")
                
            except Exception as e:
                print(f"Failed to generate image: {e}")
                sys.exit(1)
                
        if args.image_cmd == "generate":
            asyncio.run(run_generate())
    elif args.command == "run":
        from initials_agent.agent import RunOptions
        from initials_agent.db.models import Base
        from initials_agent.db.session import get_engine, get_session_factory
        from initials_agent.runtime import build_agent

        async def run_agent():
            db_url = "sqlite:///:memory:" if args.dry_run else "sqlite:///initials_agent.db"
            engine = get_engine(db_url)
            Base.metadata.create_all(engine)
            Session = get_session_factory(engine)
            with Session() as session:
                agent = build_agent(session)
                opts = RunOptions(
                    dry_run=args.dry_run,
                    force=args.force,
                    topic=args.topic,
                    no_image=args.no_image,
                    no_publish=args.no_publish,
                )
                try:
                    await agent.run(opts)
                except Exception as e:
                    print(f"Agent Run failed: {e}")
                    sys.exit(1)

        asyncio.run(run_agent())
        
    elif args.command == "scheduler":
        from initials_agent.db.models import Base, PipelineRunModel
        from initials_agent.db.session import get_engine, get_session_factory
        from initials_agent.scheduler import Scheduler

        engine = get_engine("sqlite:///initials_agent.db")
        Base.metadata.create_all(engine)
        Session = get_session_factory(engine)
        
        if args.sched_cmd == "start":
            async def run_start():
                scheduler = Scheduler()
                try:
                    await scheduler.start()
                except KeyboardInterrupt:
                    await scheduler.stop()
            try:
                asyncio.run(run_start())
            except KeyboardInterrupt:
                print("Scheduler stopped.")
                
        elif args.sched_cmd == "status":
            with Session() as session:
                runs = session.query(PipelineRunModel).order_by(PipelineRunModel.created_at.desc()).limit(10).all()
                if not runs:
                    print("No runs found.")
                for r in runs:
                    print(f"[{r.run_date}] Status: {r.status} | Retries: {r.retry_count} | Logs: {r.logs}")
                    
        elif args.sched_cmd == "run-now":
            async def force_run():
                scheduler = Scheduler()
                await scheduler.run_now()
            asyncio.run(force_run())
            
    elif args.command == "analytics":

        from initials_agent.db.models import Base
        from initials_agent.db.session import get_engine, get_session_factory
        from initials_agent.providers.analytics.mock import MockAnalyticsProvider
        from initials_agent.providers.llm.mock import MockLLMProvider
        from initials_agent.repositories.analytics import AnalyticsRepository
        from initials_agent.services.analytics.service import AnalyticsService
        
        engine = get_engine("sqlite:///initials_agent.db")
        Base.metadata.create_all(engine)
        Session = get_session_factory(engine)
        
        async def run_analytics():
            with Session() as session:
                repo = AnalyticsRepository(session)
                li_prov = MockAnalyticsProvider()
                ig_prov = MockAnalyticsProvider()
                llm = MockLLMProvider()
                
                svc = AnalyticsService(li_prov, ig_prov, repo, llm)
                
                if args.analytics_cmd == "sync":
                    await svc.sync_all()
                    print("Analytics sync complete.")
                elif args.analytics_cmd == "report":
                    try:
                        profile = await svc.generate_report()
                        print(f"Report generated! Strategy Profile ID: {profile.id}")
                        print(f"Strongest topics: {profile.strongest_topics}")
                    except ValueError as e:
                        print(f"Failed to generate report: {e}")
                        
        asyncio.run(run_analytics())

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
