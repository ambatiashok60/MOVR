from app.ai_workspace.domain.model_metadata import ModelCatalog, ModelLimits, ModelMetadata, ModelRuntimeConfiguration


class ModelCatalogService:
    """Returns model/provider data for the frontend's model selector and settings panel.
    Never calls a model — this is metadata only, sourced from the existing configuration
    layer (ModelsConfigurationDAO, per the existing ModelClientFactory architecture).

    UNCONFIRMED: nothing in the screenshots this session was built from showed a method for
    listing a tenant's *available* models (as opposed to their currently-configured one) — see
    app/integrations/existing_model_client/README.md. `_placeholder_catalog` below is a stand-in
    until that read path is identified; replace it with the real DAO call.
    """

    def __init__(self, db, tenant_id: str):
        self._db = db
        self._tenant_id = tenant_id

    def get_catalog(self) -> ModelCatalog:
        return self._placeholder_catalog()

    def update_runtime_config(self, selected_model_id: str) -> ModelRuntimeConfiguration:
        # UNCONFIRMED: no known write path for "which model is currently selected" per tenant —
        # assumed to be a ModelsConfigurationDAO update, not implemented here.
        return ModelRuntimeConfiguration(selected_model_id=selected_model_id)

    def _placeholder_catalog(self) -> ModelCatalog:
        default_model = ModelMetadata(
            id="default",
            display_name="Default (tenant-configured)",
            provider_id="unconfirmed",
            limits=ModelLimits(context_window_tokens=128_000, max_output_tokens=8_192),
            is_default=True,
        )
        return ModelCatalog(
            models=[default_model],
            runtime=ModelRuntimeConfiguration(selected_model_id=default_model.id),
        )
