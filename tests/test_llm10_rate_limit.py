"""LLM10 — Unbounded Consumption: rate limit por cliente y límites de tamaño."""
from tests.conftest import KEY_A, KEY_B, chat


def test_antes_sin_limite_todas_pasan(crear_cliente):
    cliente, _ = crear_cliente(mitigation_llm10=False)
    codigos = [chat(cliente, f"consulta {i}").status_code for i in range(15)]
    assert codigos.count(200) == 15


def test_despues_limite_por_cliente(crear_cliente):
    cliente, _ = crear_cliente(mitigation_llm10=True)
    codigos = [chat(cliente, f"consulta {i}").status_code for i in range(15)]
    assert codigos[:10] == [200] * 10
    assert set(codigos[10:]) == {429}
    # El límite es por API key: cliente-b no se ve afectado por el consumo de cliente-a.
    assert chat(cliente, "consulta", key=KEY_B).status_code == 200


def test_despues_prompt_demasiado_largo(crear_cliente):
    cliente, _ = crear_cliente(mitigation_llm10=True, max_prompt_chars=100)
    assert chat(cliente, "x" * 101).status_code == 413


def test_sin_api_key_valida_401(crear_cliente):
    cliente, _ = crear_cliente()
    assert chat(cliente, "hola", key="key-inventada").status_code == 401
