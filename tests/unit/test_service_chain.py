from rpg_engine_api.app import create_app
from rpg_engine_api.application.complete_service import CompleteEngineService
from rpg_engine_api.application.extension_service import ExtensionEngineService
from rpg_engine_api.application.production_release_service import ProductionReleaseEngineService
from rpg_engine_api.application.release_service import ReleaseCandidateEngineService
from rpg_engine_api.config import Settings


def test_application_service_chain_imports_without_cycle() -> None:
    app = create_app(Settings())
    engine = app.state.engine
    assert isinstance(engine, ProductionReleaseEngineService)
    assert isinstance(engine, ExtensionEngineService)
    assert isinstance(engine, CompleteEngineService)
    assert isinstance(engine, ReleaseCandidateEngineService)
    capability = engine.capability_projection()["data"]
    assert "campaign_drafts" in capability["features"]
    assert "classes_subclasses" in capability["features"]
    assert "trusted_extension_registry" in capability["features"]
    assert "portable_campaign_package" in capability["features"]
