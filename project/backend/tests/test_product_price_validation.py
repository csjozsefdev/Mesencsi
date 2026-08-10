from pydantic import ValidationError

from models import ProductCreate, ProductUpdate


POSTGRES_INTEGER_MAX = 2_147_483_647


def _price_error(exc: ValidationError) -> bool:
    return any(error["loc"] == ("price",) for error in exc.errors())


def test_product_create_rejects_price_above_database_limit() -> None:
    try:
        ProductCreate(
            name="Túl nagy ár teszt",
            price=POSTGRES_INTEGER_MAX + 1,
            description="Regressziós teszt.",
        )
    except ValidationError as exc:
        assert _price_error(exc)
    else:
        raise AssertionError("A túl nagy termékárat a modell elfogadta.")


def test_product_update_rejects_price_above_database_limit() -> None:
    try:
        ProductUpdate(price=POSTGRES_INTEGER_MAX + 1)
    except ValidationError as exc:
        assert _price_error(exc)
    else:
        raise AssertionError("A túl nagy módosított termékárat a modell elfogadta.")
