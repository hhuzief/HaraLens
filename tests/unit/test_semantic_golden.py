import pandas as pd

from haralens.semantic import SemanticType, infer_semantic_types


def inferred_types(table: pd.DataFrame) -> dict[str, SemanticType]:
    profile = infer_semantic_types(table)
    return {column.column_name: column.semantic_type for column in profile.columns}


def test_customer_dataset_golden_semantic_types() -> None:
    table = pd.DataFrame(
        {
            "CustomerID": range(1001, 1013),
            "Age": [22, 35, 41, 35, 52, 22, 29, 41, 33, 52, 29, 33],
            "Gender": ["Female", "Male"] * 6,
            "AnnualIncome": [
                51_250.25,
                63_100.50,
                72_800.75,
                59_900.25,
                81_200.50,
                47_300.75,
            ]
            * 2,
            "SignupDate": [f"2026-01-{day:02d}" for day in range(1, 13)],
            "IsActive": [True, False] * 6,
            "Region": ["North", "South", "West"] * 4,
            "CustomerComment": [
                f"Customer {index} provided a detailed comment about delivery and product support."
                for index in range(12)
            ],
        }
    )
    assert inferred_types(table) == {
        "CustomerID": SemanticType.IDENTIFIER,
        "Age": SemanticType.NUMERIC_DISCRETE,
        "Gender": SemanticType.CATEGORICAL,
        "AnnualIncome": SemanticType.NUMERIC_CONTINUOUS,
        "SignupDate": SemanticType.DATETIME,
        "IsActive": SemanticType.BOOLEAN,
        "Region": SemanticType.CATEGORICAL,
        "CustomerComment": SemanticType.FREE_TEXT,
    }


def test_loan_dataset_golden_semantic_types() -> None:
    table = pd.DataFrame(
        {
            "Loan_ID": [f"LN-{index:05d}" for index in range(12)],
            "ApplicantIncome": range(2_000, 8_000, 500),
            "Credit_History": [0, 1] * 6,
            "Property_Area": ["Urban", "Rural", "Semiurban"] * 4,
            "Loan_Status": ["Approved", "Rejected"] * 6,
        }
    )
    assert inferred_types(table) == {
        "Loan_ID": SemanticType.IDENTIFIER,
        "ApplicantIncome": SemanticType.NUMERIC_CONTINUOUS,
        "Credit_History": SemanticType.NUMERIC_DISCRETE,
        "Property_Area": SemanticType.CATEGORICAL,
        "Loan_Status": SemanticType.CATEGORICAL,
    }
