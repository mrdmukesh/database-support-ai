from pathlib import Path


def test_deployment_enables_existing_keyvault_for_update_and_create() -> None:
    workflow = Path(".github/workflows/azure-container-app.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count('"FEATURE_KEYVAULT_SECRETS_ENABLED=true"') == 2
    assert workflow.count(
        '"AZURE_KEY_VAULT_URL=https://${AZURE_KEY_VAULT_NAME}.vault.azure.net/"'
    ) == 2
    assert "FEATURE_KEYVAULT_SECRETS_ENABLED=false" not in workflow
