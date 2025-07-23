from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
import pandas as pd
import numpy as np

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "API is running"}

@app.get("/data", response_class=ORJSONResponse)
def read_excel_data():
    try:
        df = pd.read_excel("fichier_client.xlsx", sheet_name="Données socio-démographiques")

        # Supprimer colonnes "Unnamed"
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df.columns = df.columns.str.strip()

        colonnes_utiles = [
            "Nom du client", "Nom du fournisseur", "Âge", "Sexe", "Provenance",
            "Catégorie socio-professionnelle", "Montant reçu", "Date 1",
            "Montant payé", "Date 2"
        ]
        df = df[[col for col in colonnes_utiles if col in df.columns]]

        # Nettoyer inf / -inf -> None
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df = df.where(pd.notnull(df), None)

        # Convertir les datetime en string (orjson gère ça mais c'est plus propre)
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime("%d/%m/%Y")

        data = df.to_dict(orient="records")
        return data

    except Exception as e:
        return {"error": str(e)}
