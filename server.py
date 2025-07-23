from fastapi import FastAPI
import pandas as pd
import numpy as np

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "API is running"}

@app.get("/data")
def read_excel_data():
    try:
        df = pd.read_excel("fichier_client.xlsx", sheet_name="Données socio-démographiques")
        
        # Remplacer les valeurs inf, -inf par None (JSON compatible)
        df = df.replace([np.inf, -np.inf], np.nan)
        
        # Remplacer les NaN par None pour JSON
        df = df.where(pd.notnull(df), None)
        
        data_preview = df.head().to_dict(orient="records")
        return {"preview": data_preview}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}





