import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import locale
from datetime import datetime

# Locale française
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR')  # version simplifiée (Unix)
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'French_France.1252')  # Windows
        except locale.Error:
            locale.setlocale(locale.LC_TIME, '')  # fallback sur la locale par défaut


# ----------------------- CONFIGURATION -----------------------
st.set_page_config(layout="wide")
st.title("📊 Suivi des transactions clients & fournisseurs")

# ----------------------- IDENTIFIANTS -----------------------
clients_mdp = {
    "client1": "mdpclient1",
    "client2": "secret123",
    "client3": "azerty"
}

# ----------------------- AUTHENTIFICATION -----------------------
st.sidebar.header("🔐 Authentification client")
client_choisi = st.sidebar.text_input("Identifiant client :")
mdp_entre = st.sidebar.text_input("Mot de passe :", type="password")

if "authentifie" not in st.session_state:
    st.session_state["authentifie"] = False

if not st.session_state["authentifie"]:
    if st.sidebar.button("Se connecter"):
        if client_choisi in clients_mdp and mdp_entre == clients_mdp[client_choisi]:
            st.session_state["authentifie"] = True
            st.session_state["client"] = client_choisi
            st.sidebar.success("✅ Authentification réussie")
        else:
            st.sidebar.error("❌ Identifiants incorrects")
    else:
        st.warning("Veuillez vous authentifier pour accéder à l’application.")
        st.stop()
else:
    st.sidebar.success(f"Connecté en tant que : {st.session_state['client']}")

# ----------------------- UPLOAD DU FICHIER -----------------------
st.sidebar.markdown("---")
fichier_upload = st.sidebar.file_uploader("📤 Importez votre fichier Excel :", type=["xlsx", "xls"])

if not fichier_upload:
    st.warning("Veuillez téléverser un fichier Excel.")
    st.stop()

# ----------------------- CHARGEMENT DU FICHIER -----------------------
try:
    df = pd.read_excel(fichier_upload, sheet_name="Données socio-démographiques")
except Exception as e:
    st.error(f"Erreur de chargement : {e}")
    st.stop()

df["Date 1"] = pd.to_datetime(df["Date 1"], errors="coerce")
df["Date 2"] = pd.to_datetime(df["Date 2"], errors="coerce")

# ----------------------- FILTRAGE PAR MOIS -----------------------
mois_recu = df["Date 1"].dropna().dt.to_period("M")
mois_paye = df["Date 2"].dropna().dt.to_period("M")

mois_disponibles = pd.Series(list(set(mois_recu.tolist() + mois_paye.tolist())))
mois_disponibles = mois_disponibles.sort_values()

mois_labels = [m.strftime("%B %Y").capitalize() for m in mois_disponibles]
mois_mapping = dict(zip(mois_labels, mois_disponibles))

st.subheader("📅 Choisissez un ou plusieurs mois")
options_mois = ["Toute la période"] + mois_labels
selection = st.multiselect("Sélectionnez une ou plusieurs périodes :", options_mois, default=["Toute la période"])

if "Toute la période" in selection or not selection:
    df_recu = df[df["Montant reçu"].notna()].copy()
    df_paye = df[df["Montant payé"].notna()].copy()
    periode_label = "Toute la période"
else:
    mois_choisis = [mois_mapping[sel] for sel in selection if sel in mois_mapping]
    filtre_recu = df["Date 1"].dt.to_period("M").isin(mois_choisis)
    filtre_paye = df["Date 2"].dt.to_period("M").isin(mois_choisis)
    df_recu = df[filtre_recu & df["Montant reçu"].notna()].copy()
    df_paye = df[filtre_paye & df["Montant payé"].notna()].copy()
    periode_label = ", ".join(selection)

# ----------------------- INDICATEURS -----------------------
montant_recu_total = df_recu["Montant reçu"].sum(skipna=True)
montant_paye_total = df_paye["Montant payé"].sum(skipna=True)
solde = montant_recu_total - montant_paye_total
nb_clients = df_recu["Nom du client"].nunique()
nb_fournisseurs = df_paye["Nom du fournisseur"].nunique()

# CSS pour modifier la taille des polices dans les métriques Streamlit
st.markdown("""
    <style>
    /* Labels des indicateurs (ex: Montant reçu) */
    div[data-testid="metric-container"] > div:nth-child(1) {
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    /* Valeurs des métriques (chiffres et unité) */
    div[data-testid="metric-container"] > div:nth-child(2) {
        font-size: 18px !important;
        font-weight: 600 !important;
    }
    </style>
    """, unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Montant reçu", f"{montant_recu_total:.2f} EUR")
col2.metric("💸 Montant payé", f"{montant_paye_total:.2f} EUR")
col3.metric("📈 Solde", f"{solde:.2f} EUR")
col4.metric("👥 Clients", f"{nb_clients}")
col5.metric("🏭 Fournisseurs", f"{nb_fournisseurs}")

# ----------------------- GRAPHIQUE -----------------------
df_graph = df.copy()
df_graph["Mois"] = df_graph["Date 1"].combine_first(df_graph["Date 2"]).dt.to_period("M").dt.to_timestamp()

graph_grouped = df_graph.groupby("Mois").agg({
    "Montant reçu": "sum",
    "Montant payé": "sum"
}).fillna(0)

graph_grouped["Solde"] = graph_grouped["Montant reçu"] - graph_grouped["Montant payé"]
graph_grouped = graph_grouped.sort_index()

fig, ax = plt.subplots()
graph_grouped.index = graph_grouped.index.to_series().dt.strftime('%B %Y').str.capitalize()
graph_grouped[["Montant reçu", "Montant payé", "Solde"]].plot(kind="bar", ax=ax)
plt.xticks(rotation=45)
plt.xlabel("Mois")
plt.ylabel("Montant (€)")
plt.title("Évolution mensuelle")
plt.tight_layout()

st.subheader("📊 Évolution mensuelle")
st.pyplot(fig)

# ----------------------- COMMENTAIRE -----------------------
st.subheader("🗣️ Laissez un commentaire pour cette période")
commentaire_client = st.text_area("Vos remarques à joindre au rapport PDF :", height=150)
if st.button("🗑️ Supprimer le commentaire"):
    commentaire_client = ""
    st.experimental_rerun()

# ----------------------- GÉNÉRATION PDF -----------------------
def generer_pdf(periode_label, df_recu, df_paye, commentaire_client, nb_clients, nb_fournisseurs, montant_recu_total, montant_paye_total, solde):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Rapport - {periode_label}", ln=True)
    pdf.set_font("Arial", "", 12)
    date_rapport = datetime.today().strftime("%d/%m/%Y")
    pdf.cell(0, 10, f"Date d'émission : {date_rapport}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Nombre de clients : {nb_clients}", ln=True)
    pdf.cell(0, 10, f"Nombre de fournisseurs : {nb_fournisseurs}", ln=True)
    pdf.cell(0, 10, f"Montant reçu total : {montant_recu_total:.2f} EUR", ln=True)
    pdf.cell(0, 10, f"Montant payé total : {montant_paye_total:.2f} EUR", ln=True)
    pdf.cell(0, 10, f"Solde : {solde:.2f} EUR", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Détail des montants reçus par client :", ln=True)
    pdf.set_font("Arial", "", 12)
    for _, row in df_recu.iterrows():
        date_str = row["Date 1"].strftime("%d/%m/%Y") if not pd.isna(row["Date 1"]) else ""
        montant_str = f"{row['Montant reçu']:.2f} EUR"
        pdf.cell(0, 10, f"{row['Nom du client']} : {montant_str} le {date_str}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Détail des montants payés par fournisseur :", ln=True)
    pdf.set_font("Arial", "", 12)
    for _, row in df_paye.iterrows():
        date_str = row["Date 2"].strftime("%d/%m/%Y") if not pd.isna(row["Date 2"]) else ""
        montant_str = f"{row['Montant payé']:.2f} EUR"
        pdf.cell(0, 10, f"{row['Nom du fournisseur']} : {montant_str} le {date_str}", ln=True)

    if commentaire_client:
        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Commentaire ajouté :", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, commentaire_client)

    return pdf.output(dest='S').encode('latin1')

if st.button("📄 Générer le rapport PDF"):
    pdf_bytes = generer_pdf(
        periode_label,
        df_recu,
        df_paye,
        commentaire_client,
        nb_clients,
        nb_fournisseurs,
        montant_recu_total,
        montant_paye_total,
        solde
    )
    st.success("✅ Rapport généré avec succès.")
    st.download_button("⬇️ Télécharger le rapport PDF", data=pdf_bytes, file_name="rapport.pdf", mime="application/pdf")
