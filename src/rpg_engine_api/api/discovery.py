from fastapi import APIRouter, Request

from rpg_engine_api.api.contracts import api_response

router = APIRouter(prefix="/api/v1", tags=["discovery"])


@router.get("/discovery")
async def discovery(request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    capabilities = engine.capability_projection()["data"]
    data = {
        "api": {
            "version": "v1",
            "stability": "development",
            "deprecation_policy": "additive changes within v1; incompatible transport changes require a new API version",
            "idempotency": "retry mutating commands with the same idempotency_key and identical semantic payload",
        },
        "capabilities": capabilities,
        "creator": {
            "definition_types": [
                "npc_template", "encounter_template", "item", "quest_template", "narration_template",
                "dialogue", "faction", "vendor", "recipe", "class", "subclass", "species", "background", "feature", "ability",
            ],
            "workflow": ["workspace", "draft", "validate", "quality", "publish", "simulate", "playtest"],
            "content_is_data_only": True,
            "trusted_extensions_are_separate": True,
        },
        "ui": {
            "dynamic_action_labels": True,
            "recommended_controls_are_hints_only": True,
            "clients_must_query_available_actions": True,
            "clients_must_not_reimplement_hidden_legality": True,
        },
        "localization": {
            "default_locale": "en",
            "label_keys_supported": True,
            "client_fallback_to_display_text": True,
        },
        "units": {
            "simulation_time": "engine_time_unit",
            "distance": "ruleset_defined",
            "currency": "ruleset_or_campaign_defined",
            "clients_must_not_assume_real_world_units": True,
        },
        "assets": {
            "references_are_opaque": True,
            "inline_binary_assets": False,
            "pack_scoped_assets_planned": True,
        },
        "live": {
            "websocket": "/api/v1/ws/campaigns/{campaign_id}",
            "resume": True,
            "snapshot_delta_sync": True,
            "authoritative_events_never_silently_dropped": True,
        },
    }
    return api_response(request, data)
