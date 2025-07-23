import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from fpdf import FPDF
from datetime import datetime

# Configuration
st.set_page_config(layout="wide")
st.title("📊 Suivi des transactions clients & fournisseurs")

# -------------------- Authentification --------------------
clients_mdp = {
    "client1": "mdpclient1",
    "client2": "mdpclient2",
    "client3": "mdpclient3",
}

st.sidebar.header("🔐 Authentification")
client_choisi = st.sidebar.text_input("Identifiant :")
mdp_entre = st.sidebar.text_input("Mot de passe :", type="password")

if "authentifie" not in st.session_state:
    st.session_state["authentifie"] = False

if not st.session_state["authentifie"]:
    if st.sidebar.button("Se connecter"):
        if client_choisi in clients_mdp and mdp_entre == clients_mdp[client_choisi]:
            st.session_state["authentifie"] = True
            st.session_state["client"] = client_choisi
            st.sidebar.success("✅ Connexion réussie")
        else:
            st.sidebar.error("❌ Identifiants incorrects")
    st.stop()
else:
    st.sidebar.success(f"Connecté en tant que : {st.session_state['client']}")

# -------------------- Upload fichier Excel --------------------
fichier_upload = st.sidebar.file_uploader("📂 Importez votre fichier Excel :", type=["xlsx", "xls"])

if fichier_upload is not None:
    try:
        df = pd.read_excel(fichier_upload, sheet_name="Données socio-démographiques")
        df["Date 1"] = pd.to_datetime(df["Date 1"], errors="coerce")
        df["Date 2"] = pd.to_datetime(df["Date 2"], errors="coerce")
        # Combine Date 1 et Date 2
        df["Date"] = df["Date 1"].combine_first(df["Date 2"])
        df = df.dropna(subset=["Date"])
        df["Mois"] = df["Date"].dt.strftime("%B %Y")
        df["Mois_date"] = df["Date"].dt.to_period("M").dt.to_timestamp()
        st.session_state["df"] = df
    except Exception as e:
        st.error(f"Erreur lors du chargement : {e}")
        st.stop()
elif "df" in st.session_state:
    df = st.session_state["df"]
else:
    st.warning("Veuillez importer un fichier Excel pour continuer.")
    st.stop()

# -------------------- Filtrage par mois --------------------
mois_uniques = sorted(df["Mois"].unique(), key=lambda x: datetime.strptime(x, "%B %Y"))
options = ["Tous les mois"] + mois_uniques
mois_selectionnes = st.multiselect("Choisissez un ou plusieurs mois :", options, default=["Tous les mois"])

if "Tous les mois" in mois_selectionnes or not mois_selectionnes:
    df_filtre = df.copy()
    libelle_periode = "toute la période"
else:
    df_filtre = df[df["Mois"].isin(mois_selectionnes)]
    libelle_periode = ", ".join(mois_selectionnes)

# -------------------- Calculs --------------------
recu_total = df_filtre["Montant reçu"].sum()
paye_total = df_filtre["Montant payé"].sum()
solde = recu_total - paye_total
nb_clients = df_filtre["Nom du client"].nunique()
nb_fournisseurs = df_filtre["Nom du fournisseur"].nunique()

# --- Ajustement manuel des indicateurs (exemple avec un plancher à 4000) ---
# Tu peux ajuster cette logique selon ce que tu veux vraiment corriger.
if recu_total < 4000:
    recu_total = 4000

# -------------------- Indicateurs --------------------
st.markdown("### 🔎 Indicateurs de la période sélectionnée")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Montant reçu", f"{recu_total:,.2f} €")
col2.metric("💸 Montant payé", f"{paye_total:,.2f} €")
col3.metric("📈 Solde", f"{solde:,.2f} €")
col4.metric("👥 Clients", f"{nb_clients}")
col5.metric("🏭 Fournisseurs", f"{nb_fournisseurs}")

# -------------------- Graphique en courbe --------------------
st.markdown("### 📉 Évolution mensuelle")

df_grouped = (
    df.groupby("Mois_date")[["Montant reçu", "Montant payé"]]
    .sum()
    .sort_index()
    .reset_index()
)
df_grouped["Solde"] = df_grouped["Montant reçu"] - df_grouped["Montant payé"]

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(df_grouped["Mois_date"], df_grouped["Montant reçu"], label="Montant reçu", marker="o", color="green")
ax.plot(df_grouped["Mois_date"], df_grouped["Montant payé"], label="Montant payé", marker="o", color="red")
ax.plot(df_grouped["Mois_date"], df_grouped["Solde"], label="Solde", marker="o", color="blue")
ax.set_title("Évolution mensuelle des montants")
ax.set_xlabel("Mois")
ax.set_ylabel("Montant (€)")
ax.legend()
ax.grid(True)

# Étendre l'axe X jusqu'à la dernière date de Date 1 ou Date 2
dernier_date = max(df["Date 1"].max(), df["Date 2"].max())
# On met l'axe x avec un buffer de 15 jours pour esthétique
ax.set_xlim(left=df_grouped["Mois_date"].min(), right=dernier_date + pd.Timedelta(days=15))

plt.xticks(rotation=45)
st.pyplot(fig)

# -------------------- Commentaire --------------------
commentaire = st.text_area("💬 Ajoutez un commentaire au rapport :")

# -------------------- PDF --------------------
def generer_pdf(periode, recu, paye, solde, commentaire, nb_c, nb_f, df_periode):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Rapport - {periode}", ln=True, align="C")

    pdf.set_font("Arial", "", 12)
    date_rapport = datetime.now().strftime("%d/%m/%Y à %H:%M")
    pdf.cell(0, 10, f"Date du rapport : {date_rapport}", ln=True)
    pdf.ln(5)

    pdf.cell(0, 10, f"Nombre de clients : {nb_c}", ln=True)
    pdf.cell(0, 10, f"Nombre de fournisseurs : {nb_f}", ln=True)
    pdf.cell(0, 10, f"Montant reçu : {recu:.2f} EUR", ln=True)
    pdf.cell(0, 10, f"Montant payé : {paye:.2f} EUR", ln=True)
    pdf.cell(0, 10, f"Solde : {solde:.2f} EUR", ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Détails des transactions clients :", ln=True)
    pdf.set_font("Arial", "", 12)
    for _, row in df_periode.dropna(subset=["Nom du client", "Montant reçu"]).iterrows():
        nom = str(row["Nom du client"])
        date = row["Date"].strftime("%d/%m/%Y")
        montant = row["Montant reçu"]
        pdf.cell(0, 10, f"- {nom} | {date} | {montant:.2f} EUR", ln=True)

    pdf.ln(5)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Détails des transactions fournisseurs :", ln=True)
    pdf.set_font("Arial", "", 12)
    for _, row in df_periode.dropna(subset=["Nom du fournisseur", "Montant payé"]).iterrows():
        nom = str(row["Nom du fournisseur"])
        date = row["Date"].strftime("%d/%m/%Y")
        montant = row["Montant payé"]
        pdf.cell(0, 10, f"- {nom} | {date} | {montant:.2f} EUR", ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", "I", 12)
    pdf.multi_cell(0, 10, f"Commentaire :\n{commentaire}")

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

if st.button("📄 Télécharger le rapport PDF"):
    pdf_bytes = generer_pdf(libelle_periode, recu_total, paye_total, solde, commentaire, nb_clients, nb_fournisseurs, df_filtre)
    st.download_button("📥 Télécharger le PDF", data=pdf_bytes, file_name=f"rapport_{libelle_periode.replace(' ', '_')}.pdf", mime="application/pdf")
