import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import locale
from supabase import create_client, Client
import bcrypt
from datetime import datetime
import os

# Locale française
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'French_France.1252')
    except locale.Error:
        pass

# -------------------- CONFIG SUPABASE --------------------
SUPABASE_URL = "https://uuualzegrflxaypalcmk.supabase.co"  # ⬅️ À remplacer
SUPABASE_KEY = os.getenv("SUPABASE_KEY");
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------- SESSION --------------------
if "authentifie" not in st.session_state:
    st.session_state["authentifie"] = False

# -------------------- AUTH FUNCTIONS --------------------
def inscrire_utilisateur(username, password):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    exist = supabase.table("users").select("username").eq("username", username).execute()
    if exist.data and len(exist.data) > 0:
        st.sidebar.error("❌ Identifiant déjà pris.")
        return
    supabase.table("users").insert({
        "username": username,
        "password_hash": hashed
    }).execute()
    st.sidebar.success("✅ Compte créé. Veuillez vous connecter.")

def verifier_utilisateur(username, password):
    result = supabase.table("users").select("password_hash").eq("username", username).execute()
    if not result.data or len(result.data) == 0:
        return False
    hashed = result.data[0]["password_hash"].encode("utf-8")
    return bcrypt.checkpw(password.encode("utf-8"), hashed)

# -------------------- UI AUTH --------------------
st.sidebar.title("🔐 Connexion client")
choix = st.sidebar.radio("Action :", ["Se connecter", "Créer un compte"])
username = st.sidebar.text_input("Identifiant")
password = st.sidebar.text_input("Mot de passe", type="password")

if not st.session_state["authentifie"]:
    if choix == "Créer un compte":
        if st.sidebar.button("Créer mon compte"):
            if username and password:
                inscrire_utilisateur(username, password)
            else:
                st.sidebar.warning("Veuillez remplir les deux champs.")
        st.stop()
    elif choix == "Se connecter":
        if st.sidebar.button("Se connecter"):
            if verifier_utilisateur(username, password):
                st.session_state["authentifie"] = True
                st.session_state["client"] = username
                st.sidebar.success(f"✅ Connecté : {username}")
            else:
                st.sidebar.error("❌ Identifiants incorrects.")
        st.stop()
else:
    st.sidebar.success(f"Connecté : {st.session_state['client']}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state["authentifie"] = False
        st.session_state["client"] = None
        st.experimental_rerun()

# ----------------------- CHARGEMENT DU FICHIER -----------------------
fichier_upload = st.file_uploader("📂 Importez votre fichier Excel", type=["xls", "xlsx"])

if fichier_upload is None:
    st.info("Veuillez importer un fichier pour continuer.")
    st.stop()

try:
    df = pd.read_excel(fichier_upload, sheet_name="Données socio-démographiques")
except Exception as e:
    st.error(f"Erreur de chargement : {e}")
    st.stop()

# ----------------------- FILTRAGE PAR MOIS -----------------------
df["Date 1"] = pd.to_datetime(df["Date 1"], errors='coerce')
df["Date 2"] = pd.to_datetime(df["Date 2"], errors='coerce')

mois_recu = df["Date 1"].dropna().dt.to_period("M")
mois_paye = df["Date 2"].dropna().dt.to_period("M")

mois_disponibles = pd.Series(pd.concat([mois_recu, mois_paye]).unique())
mois_disponibles = mois_disponibles.sort_values()

mois_labels = [m.to_timestamp().strftime("%b %Y").capitalize() for m in mois_disponibles]  # 3 lettres mois
mois_mapping = dict(zip(mois_labels, mois_disponibles))

st.subheader("📅 Choisissez un ou plusieurs mois")
options_mois = ["Toute la période"] + mois_labels
selection = st.multiselect("Sélectionnez une ou plusieurs périodes :", options_mois, default=["Toute la période"])

if "Toute la période" in selection or not selection:
    # Pas de filtrage, on prend tout
    df_filtre = df.copy()
    periode_label = "Toute la période"
else:
    mois_choisis = [mois_mapping[sel] for sel in selection if sel in mois_mapping]

    # On garde les lignes dont Date 1 ou Date 2 est dans l'un des mois choisis
    filtre_date1 = df["Date 1"].dt.to_period("M").isin(mois_choisis)
    filtre_date2 = df["Date 2"].dt.to_period("M").isin(mois_choisis)
    df_filtre = df[(filtre_date1 | filtre_date2)].copy()
    periode_label = ", ".join(selection)

# ---------------- Filtrage et calcul des indicateurs sur df_recu et df_paye ----------------
df_recu = df_filtre[df_filtre["Montant reçu"].notna() & (df_filtre["Montant reçu"] > 0)].copy()
df_paye = df_filtre[df_filtre["Montant payé"].notna() & (df_filtre["Montant payé"] > 0)].copy()

if "Toute la période" not in selection and selection:
    df_recu = df_recu[df_recu["Date 1"].dt.to_period("M").isin(mois_choisis)]
    df_paye = df_paye[df_paye["Date 2"].dt.to_period("M").isin(mois_choisis)]

montant_recu_total = df_recu["Montant reçu"].sum()
montant_paye_total = df_paye["Montant payé"].sum()
solde = montant_recu_total - montant_paye_total
nb_clients = df_recu["Nom du client"].nunique()
nb_fournisseurs = df_paye["Nom du fournisseur"].nunique()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Montant reçu", f"{montant_recu_total:.2f} EUR")
col2.metric("💸 Montant payé", f"{montant_paye_total:.2f} EUR")
col3.metric("📈 Solde", f"{solde:.2f} EUR")
col4.metric("👥 Clients", f"{nb_clients}")
col5.metric("🏭 Fournisseurs", f"{nb_fournisseurs}")

# ----------------------- GRAPHIQUE FILTRÉ -----------------------
df_graph = df_filtre.copy()
df_graph["Date 1"] = pd.to_datetime(df_graph["Date 1"], errors='coerce')
df_graph["Date 2"] = pd.to_datetime(df_graph["Date 2"], errors='coerce')
df_graph["Date_combined"] = df_graph[["Date 1", "Date 2"]].min(axis=1, skipna=True)
df_graph["Mois"] = df_graph["Date_combined"].dt.to_period("M").dt.to_timestamp()

if not df_graph["Mois"].empty:
    # Utiliser mois_choisis si filtrage activé, sinon tous les mois
    if "Toute la période" in selection or not selection:
        mois_a_afficher = sorted(df_graph["Mois"].dropna().unique())
    else:
        # Convertion des périodes mois_choisis en timestamp
        mois_a_afficher = sorted([m.to_timestamp() for m in mois_choisis])

    graph_grouped = df_graph.groupby("Mois").agg({
        "Montant reçu": "sum",
        "Montant payé": "sum"
    }).reindex(mois_a_afficher, fill_value=0)

    graph_grouped["Solde"] = graph_grouped["Montant reçu"] - graph_grouped["Montant payé"]
    graph_grouped = graph_grouped.sort_index()

    fig, ax = plt.subplots()
    graph_grouped.index = graph_grouped.index.to_series().dt.strftime('%b %Y').str.capitalize()
    graph_grouped[["Montant reçu", "Montant payé", "Solde"]].plot(kind="bar", ax=ax)
    plt.xticks(rotation=45, fontsize=8)
    plt.xlabel("Mois")
    plt.ylabel("Montant (€)")
    plt.title("Évolution mensuelle")
    plt.tight_layout()

    st.subheader("📊 Évolution mensuelle")
    st.pyplot(fig)
else:
    st.info("Aucune donnée trouvée")

# ----------------------- COMMENTAIRE -----------------------
st.subheader("🗣️ Laissez un commentaire pour cette période")
commentaire_client = st.text_area("Vos remarques à joindre au rapport PDF :", height=150)
if st.button("🗑️ Supprimer le commentaire"):
    commentaire_client = ""
    st.experimental_rerun()

# ----------------------- GÉNÉRATION PDF -----------------------
def generer_pdf(periode_label, df_recu, df_paye, commentaire_client, nb_clients, nb_fournisseurs, montant_recu_total, montant_paye_total, solde):
    from fpdf import FPDF
    from datetime import datetime
    
    df_recu["Date 1"] = pd.to_datetime(df_recu["Date 1"], errors="coerce")
    df_paye["Date 2"] = pd.to_datetime(df_paye["Date 2"], errors="coerce")
    
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

    if not df_recu.empty:
        meilleur_client = df_recu.groupby("Nom du client")["Montant reçu"].sum().idxmax()
        montant_meilleur_client = df_recu.groupby("Nom du client")["Montant reçu"].sum().max()
        pdf.cell(0, 10, f"Meilleur client : {meilleur_client} ({montant_meilleur_client:.2f} EUR)", ln=True)
    else:
        pdf.cell(0, 10, "Meilleur client : N/A", ln=True)

    if not df_paye.empty:
        meilleur_fournisseur = df_paye.groupby("Nom du fournisseur")["Montant payé"].sum().idxmax()
        montant_meilleur_fournisseur = df_paye.groupby("Nom du fournisseur")["Montant payé"].sum().max()
        pdf.cell(0, 10, f"Meilleur fournisseur : {meilleur_fournisseur} ({montant_meilleur_fournisseur:.2f} EUR)", ln=True)
    else:
        pdf.cell(0, 10, "Meilleur fournisseur : N/A", ln=True)

    # Solde coloré uniquement dans PDF
    if solde >= 0:
        pdf.set_text_color(0, 128, 0)
    else:
        pdf.set_text_color(255, 0, 0)
    pdf.cell(0, 10, f"Solde : {solde:.2f} EUR", ln=True)
    pdf.set_text_color(0, 0, 0)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Détail des montants reçus par client :", ln=True)
    pdf.set_font("Arial", "", 12)
    for _, row in df_recu.iterrows():
        date_str = row["Date 1"].strftime("%d/%m/%Y") if pd.notna(row["Date 1"]) else ""
        montant_str = f"{row['Montant reçu']:.2f} EUR"
        pdf.cell(0, 10, f"{row['Nom du client']} : {montant_str} le {date_str}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Détail des montants payés par fournisseur :", ln=True)
    pdf.set_font("Arial", "", 12)
    for _, row in df_paye.iterrows():
        date_str = row["Date 2"].strftime("%d/%m/%Y") if pd.notna(row["Date 2"]) else ""
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
    st.download_button(
        label="⬇️ Télécharger le rapport PDF",
        data=pdf_bytes,
        file_name=f"rapport_{periode_label.replace(' ', '_')}.pdf",
        mime="application/pdf"
    )
