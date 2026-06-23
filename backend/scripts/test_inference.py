import sys
import os
import pandas as pd

# Dodanie ścieżki, żeby Python widział folder 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# POPRAWIONY IMPORT:
from app.services.llm_parser_service import parse_nomination_email_with_llm
from app.database import SessionLocal


def test_inference(csv_path):
    df = pd.read_csv(csv_path, sep=';')
    db = SessionLocal()

    print(f"🚀 Testowanie inferencji dla {len(df)} maili...")

    for _, row in df.iterrows():
        print(f"\n--- Test dla: {row['subject']} ---")

        # POPRAWIONE WYWOŁANIE:
        result = parse_nomination_email_with_llm(row['subject'], row['body'])

        print(f"Wynik parsowania: {result}")


if __name__ == "__main__":
    # Upewnij się, że ścieżka do pliku jest poprawna względem /workspace
    test_inference("seed/data/testowe_wybrakowane_maile.csv")