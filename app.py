import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import locale
from supabase import create_client, Client
import bcrypt
from datetime import datetime
import os
import subprocess

# Locale française
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'French_France.1252')
    except locale.Error:
        pass

# Installer Playwright browsers
try:
    subprocess.run(["playwright", "install"], check=True)
    st.write("✅ Playwright browsers installés.")
except Exception as e:
    st.error(f"Erreur lors de l'installation de Playwright : {e}")

# Configuration Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Session
if "authentifie" not in st.session_state:
    st.session_state["authentifie"] = False

# Fonctions d'authentification
def inscrire_utilisateur(email, password):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Vérifie si email existe déjà
    exist = supabase.table("users").select("email").eq("email", email).execute()
    if exist.error:
        st.sidebar.error(f"Erreur vérification utilisateur : {exist.error.message}")
        return False
    if exist.data and len(exist.data) > 0:
        st.sidebar.error("❌ Identifiant déjà pris.")
        return False

    # Insère nouvel utilisateur
    response = supabase.table("users").insert({
        "email": email,
        "password_hash": hashed
    }).execute()

    if response.error:
        st.sidebar.error(f"Erreur création compte : {response.error.message}")
        return False
    elif response.status_code != 201:
        st.sidebar.error(f"Erreur création compte, status {response.status_code}: {response.data}")
        return False
    else:
        st.sidebar.success("✅ Compte créé. Veuillez vous connecter.")
        return True

def verifier_utilisateur(email, password):
    result = supabase.table("users").select("password_hash").eq("email", email).execute()
    if result.error:
        st.sidebar.error(f"Erreur lors de la connexion : {result.error.message}")
        return False
    if not result.data or len(result.data) == 0:
        return False
    hashed = result.data[0]["password_hash"].encode("utf-8")
    return bcrypt.checkpw(password.encode("utf-8"), hashed)

# UI Auth
st.sidebar.title("🔐 Connexion client")
choix = st.sidebar.radio("Action :", ["Se connecter", "Créer un compte"])

# Pour garder la valeur des champs dans session_state et pouvoir les réinitialiser
if "email_input" not in st.session_state:
    st.session_state["email_input"] = ""
if "password_input" not in st.session_state:
    st.session_state["password_input"] = ""

email = st.sidebar.text_input("Identifiant", value=st.session_state["email_input"], key="email_input")
password = st.sidebar.text_input("Mot de passe", type="password", value=st.session_state["password_input"], key="password_input")

if not st.session_state["authentifie"]:
    if choix == "Créer un compte":
        if st.sidebar.button("Créer mon compte"):
            if email and password:
                success = inscrire_utilisateur(email, password)
                if success:
                    # Vide les champs
                    st.session_state["email_input"] = ""
                    st.session_state["password_input"] = ""
                    st.experimental_rerun()  # Recharge pour nettoyer et clarifier l'interface
            else:
                st.sidebar.warning("Veuillez remplir les deux champs.")
        st.stop()
    elif choix == "Se connecter":
        if st.sidebar.button("Se connecter"):
            if verifier_utilisateur(email, password):
                st.session_state["authentifie"] = True
                st.session_state["client"] = email
                st.sidebar.success(f"✅ Connecté : {email}")
            else:
                st.sidebar.error("❌ Identifiants incorrects.")
        st.stop()
else:
    st.sidebar.success(f"Connecté : {st.session_state['client']}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state["authentifie"] = False
        st.session_state["client"] = None
        st.experimental_rerun()

# ----------------------- PAGE NAVIGATION -----------------------
page = st.sidebar.selectbox("📄 Choisissez une page :", ["Accueil", "Filtrer par client/fournisseur", "Carte des clients", "Veille concurrentielle"])

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

# Traitement des dates
df["Date 1"] = pd.to_datetime(df["Date 1"], errors='coerce')
df["Date 2"] = pd.to_datetime(df["Date 2"], errors='coerce')

if page == "Accueil":
    st.title("Page principale")

    # ----------------------- FILTRAGE PAR MOIS -----------------------
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
    df_graph["Date_combined"] = df_graph[["Date 1", "Date 2"]].min(axis=1, skipna=True)
    df_graph["Mois"] = df_graph["Date_combined"].dt.to_period("M").dt.to_timestamp()

    if not df_graph["Mois"].empty:
        if "Toute la période" in selection or not selection:
            mois_a_afficher = sorted(df_graph["Mois"].dropna().unique())
        else:
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
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"Rapport - {periode_label}", ln=True)
        pdf.set_font("Arial", "", 12)
        date_rapport = datetime.today().strftime("%d/%m/%Y")
        pdf.cell(0, 10, f"Date du rapport : {date_rapport}", ln=True)
        pdf.ln(10)

        # Résumé des chiffres clés
        pdf.cell(0, 10, f"Montant reçu total : {montant_recu_total:.2f} EUR", ln=True)
        pdf.cell(0, 10, f"Montant payé total : {montant_paye_total:.2f} EUR", ln=True)
        pdf.cell(0, 10, f"Solde : {solde:.2f} EUR", ln=True)
        pdf.cell(0, 10, f"Nombre de clients : {nb_clients}", ln=True)
        pdf.cell(0, 10, f"Nombre de fournisseurs : {nb_fournisseurs}", ln=True)
        pdf.ln(10)

        # Commentaire utilisateur
        pdf.set_font("Arial", "I", 12)
        pdf.multi_cell(0, 10, f"Commentaires :\n{commentaire_client if commentaire_client else 'Aucun commentaire'}")
        pdf.ln(10)

        # Table Montant reçu par client
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Montants reçus par client", ln=True)
        pdf.set_font("Arial", "", 12)
        df_recu_group = df_recu.groupby("Nom du client")["Montant reçu"].sum().reset_index()
        for _, row in df_recu_group.iterrows():
            pdf.cell(0, 10, f"{row['Nom du client']}: {row['Montant reçu']:.2f} EUR", ln=True)
        pdf.ln(10)

        # Table Montant payé par fournisseur
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Montants payés par fournisseur", ln=True)
        pdf.set_font("Arial", "", 12)
        df_paye_group = df_paye.groupby("Nom du fournisseur")["Montant payé"].sum().reset_index()
        for _, row in df_paye_group.iterrows():
            pdf.cell(0, 10, f"{row['Nom du fournisseur']}: {row['Montant payé']:.2f} EUR", ln=True)
        pdf.ln(10)

        # Sauvegarde PDF dans buffer
        pdf_output_path = "/tmp/rapport_suivi.pdf"
        pdf.output(pdf_output_path)
        return pdf_output_path

    if st.button("📄 Générer le rapport PDF"):
        pdf_path = generer_pdf(periode_label, df_recu, df_paye, commentaire_client, nb_clients, nb_fournisseurs, montant_recu_total, montant_paye_total, solde)
        with open(pdf_path, "rb") as f:
            st.download_button("⬇️ Télécharger le rapport PDF", f, file_name="rapport_suivi.pdf", mime="application/pdf")

elif page == "Filtrer par client/fournisseur":
    import streamlit as st
    import pandas as pd
    from io import BytesIO
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet

    st.title("Filtrer par client et fournisseur")

    # Initialisation session_state
    if "clients_selection" not in st.session_state:
        st.session_state["clients_selection"] = []
    if "fournisseurs_selection" not in st.session_state:
        st.session_state["fournisseurs_selection"] = []

    if st.button("🔄 Réinitialiser les filtres"):
        st.session_state["clients_selection"] = []
        st.session_state["fournisseurs_selection"] = []

    clients = df["Nom du client"].dropna().unique().tolist()
    fournisseurs = df["Nom du fournisseur"].dropna().unique().tolist()

    clients_selection = st.multiselect(
        "Sélectionnez un ou plusieurs clients :",
        clients,
        default=st.session_state["clients_selection"],
        key="clients_selection"
    )

    fournisseurs_selection = st.multiselect(
        "Sélectionnez un ou plusieurs fournisseurs :",
        fournisseurs,
        default=st.session_state["fournisseurs_selection"],
        key="fournisseurs_selection"
    )

    filtre_clients = df["Nom du client"].isin(clients_selection) if clients_selection else pd.Series([False] * len(df))
    filtre_fournisseurs = df["Nom du fournisseur"].isin(fournisseurs_selection) if fournisseurs_selection else pd.Series([False] * len(df))

    # Calculs des montants totaux filtrés
    montant_recu_total = df[filtre_clients]["Montant reçu"].sum() if clients_selection else 0.0
    montant_paye_total = df[filtre_fournisseurs]["Montant payé"].sum() if fournisseurs_selection else 0.0
    solde = montant_recu_total - montant_paye_total

    # Affichage métriques (uniquement 3 premières colonnes)
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Montant reçu", f"{montant_recu_total:.2f} EUR")
    col2.metric("💸 Montant payé", f"{montant_paye_total:.2f} EUR")
    col3.metric("📈 Solde", f"{solde:.2f} EUR")

    st.subheader("📊 Statistiques synthétiques")

    if clients_selection:
        st.markdown("### 💰 Clients")
        for client in clients_selection:
            df_client = df[filtre_clients & (df["Nom du client"] == client)]
            montant_total = df_client["Montant reçu"].sum()
            nb_trans = df_client["Montant reçu"].count()
            moyenne = df_client["Montant reçu"].mean() if nb_trans > 0 else 0
            derniere_ligne = df_client.loc[df_client["Date 1"].idxmax()] if nb_trans > 0 else None
            if derniere_ligne is not None and pd.notna(derniere_ligne["Date 1"]):
                derniere_date = derniere_ligne["Date 1"].strftime('%d %B %Y')
                derniere_montant = derniere_ligne["Montant reçu"]
            else:
                derniere_date = "N/A"
                derniere_montant = 0

            st.markdown(f"""
                <div style="border:1px solid #ddd; padding:10px; margin-bottom:15px; border-radius:5px;">
                    <h4 style="margin-bottom:8px;">💰 {client}</h4>
                    <p style="font-size:16px; margin:2px 0;">💸 <b>Montant total reçu :</b> {montant_total:.2f} €</p>
                    <p style="font-size:16px; margin:2px 0;">📅 <b>Nombre de transactions :</b> {nb_trans}</p>
                    <p style="font-size:16px; margin:2px 0;">💰 <b>Moyenne par transaction :</b> {moyenne:.2f} €</p>
                    <p style="font-size:16px; margin:2px 0;">🕒 <b>Dernière transaction :</b> {derniere_date} pour {derniere_montant:.2f} €</p>
                </div>
                """, unsafe_allow_html=True)

    if fournisseurs_selection:
        st.markdown("### 🧾 Fournisseurs")
        for fournisseur in fournisseurs_selection:
            df_fournisseur = df[filtre_fournisseurs & (df["Nom du fournisseur"] == fournisseur)]
            montant_total = df_fournisseur["Montant payé"].sum()
            nb_trans = df_fournisseur["Montant payé"].count()
            moyenne = df_fournisseur["Montant payé"].mean() if nb_trans > 0 else 0
            derniere_ligne = df_fournisseur.loc[df_fournisseur["Date 2"].idxmax()] if nb_trans > 0 else None
            if derniere_ligne is not None and pd.notna(derniere_ligne["Date 2"]):
                derniere_date = derniere_ligne["Date 2"].strftime('%d %B %Y')
                derniere_montant = derniere_ligne["Montant payé"]
            else:
                derniere_date = "N/A"
                derniere_montant = 0

            st.markdown(f"""
                <div style="border:1px solid #ddd; padding:10px; margin-bottom:15px; border-radius:5px;">
                    <h4 style="margin-bottom:8px;">🧾 {fournisseur}</h4>
                    <p style="font-size:16px; margin:2px 0;">💸 <b>Montant total payé :</b> {montant_total:.2f} €</p>
                    <p style="font-size:16px; margin:2px 0;">📅 <b>Nombre de transactions :</b> {nb_trans}</p>
                    <p style="font-size:16px; margin:2px 0;">💰 <b>Moyenne par transaction :</b> {moyenne:.2f} €</p>
                    <p style="font-size:16px; margin:2px 0;">🕒 <b>Dernière transaction :</b> {derniere_date} pour {derniere_montant:.2f} €</p>
                </div>
                """, unsafe_allow_html=True)

    st.subheader("📜 Historique des transactions")

    if clients_selection:
        st.markdown("### 💰 Transactions Clients")
        for client in clients_selection:
            df_client = df[filtre_clients & (df["Nom du client"] == client)]
            for _, row in df_client.iterrows():
                date = row["Date 1"]
                montant = row["Montant reçu"]
                if pd.notna(montant) and pd.notna(date):
                    st.markdown(f"- **{client}** a payé **{montant:.2f} €** le **{date.strftime('%d %B %Y')}**")

    if fournisseurs_selection:
        st.markdown("### 🧾 Transactions Fournisseurs")
        for fournisseur in fournisseurs_selection:
            df_fournisseur = df[filtre_fournisseurs & (df["Nom du fournisseur"] == fournisseur)]
            for _, row in df_fournisseur.iterrows():
                date = row["Date 2"]
                montant = row["Montant payé"]
                if pd.notna(montant) and pd.notna(date):
                    st.markdown(f"- **{fournisseur}** a reçu **{montant:.2f} €** le **{date.strftime('%d %B %Y')}**")

    # Fonction utilitaire pour récupérer la première valeur non nulle d'une colonne client
    def get_first_valid_value(df_client, col):
        if col in df_client.columns:
            vals = df_client[col].dropna().unique()
            if len(vals) > 0:
                return vals[0]
        return "N/A"

    # ----------------------- COMMENTAIRE -----------------------
    st.subheader("🗣️ Laissez un commentaire pour ces clients et fournisseurs")
    commentaire_client = st.text_area("Vos remarques à joindre au rapport PDF :", height=150)
    if st.button("🗑️ Supprimer le commentaire"):
        commentaire_client = ""
        st.experimental_rerun()

    # Génération du PDF
if st.button("📄 Générer le PDF des données sélectionnées"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Rapport des Transactions - Clients et Fournisseurs", styles["Title"]))
    elements.append(Spacer(1, 12))

    # AJOUT DES 3 VARIABLES CLÉS EN HAUT DU PDF
    elements.append(Paragraph(f"Montant reçu total : {montant_recu_total:.2f} €", styles["Heading3"]))
    elements.append(Paragraph(f"Montant payé total : {montant_paye_total:.2f} €", styles["Heading3"]))
    elements.append(Paragraph(f"Solde : {solde:.2f} €", styles["Heading3"]))
    elements.append(Spacer(1, 12))

    # Infos Clients
    for client in clients_selection:
        df_client = df[df["Nom du client"] == client]
        montant_total = df_client["Montant reçu"].sum()
        nb_trans = df_client["Montant reçu"].count()
        moyenne = df_client["Montant reçu"].mean() if nb_trans > 0 else 0

        if nb_trans > 0:
            derniere_ligne = df_client.loc[df_client["Date 1"].idxmax()]
            derniere_date = derniere_ligne["Date 1"].strftime('%d %B %Y') if pd.notna(derniere_ligne["Date 1"]) else "N/A"
            derniere_montant = derniere_ligne["Montant reçu"]
        else:
            derniere_date = "N/A"
            derniere_montant = 0

        sexe = get_first_valid_value(df_client, "Sexe")
        age = get_first_valid_value(df_client, "Âge")
        provenance = get_first_valid_value(df_client, "Provenance")
        csp = get_first_valid_value(df_client, "Catégorie socio-professionnelle")

        elements.append(Paragraph(f"Client : {client}", styles["Heading2"]))
        elements.append(Paragraph(f"Sexe : {sexe}, Âge : {age}, Provenance : {provenance}, CSP : {csp}", styles["Normal"]))
        elements.append(Paragraph(f"Montant total reçu : {montant_total:.2f} €", styles["Normal"]))
        elements.append(Paragraph(f"Nombre de transactions : {nb_trans}", styles["Normal"]))
        elements.append(Paragraph(f"Moyenne par transaction : {moyenne:.2f} €", styles["Normal"]))
        elements.append(Paragraph(f"Dernière transaction : {derniere_date} pour {derniere_montant:.2f} €", styles["Normal"]))
        elements.append(Spacer(1, 12))

    # Infos Fournisseurs
    for fournisseur in fournisseurs_selection:
        df_fournisseur = df[df["Nom du fournisseur"] == fournisseur]
        montant_total = df_fournisseur["Montant payé"].sum()
        nb_trans = df_fournisseur["Montant payé"].count()
        moyenne = df_fournisseur["Montant payé"].mean() if nb_trans > 0 else 0

        if nb_trans > 0:
            derniere_ligne = df_fournisseur.loc[df_fournisseur["Date 2"].idxmax()]
            derniere_date = derniere_ligne["Date 2"].strftime('%d %B %Y') if pd.notna(derniere_ligne["Date 2"]) else "N/A"
            derniere_montant = derniere_ligne["Montant payé"]
        else:
            derniere_date = "N/A"
            derniere_montant = 0

        elements.append(Paragraph(f"Fournisseur : {fournisseur}", styles["Heading2"]))
        elements.append(Paragraph(f"Montant total payé : {montant_total:.2f} €", styles["Normal"]))
        elements.append(Paragraph(f"Nombre de transactions : {nb_trans}", styles["Normal"]))
        elements.append(Paragraph(f"Moyenne par transaction : {moyenne:.2f} €", styles["Normal"]))
        elements.append(Paragraph(f"Dernière transaction : {derniere_date} pour {derniere_montant:.2f} €", styles["Normal"]))
        elements.append(Spacer(1, 12))

    # Ajout du commentaire utilisateur s'il existe
    if commentaire_client.strip():
        elements.append(Paragraph("Commentaire de l'utilisateur :", styles["Heading2"]))
        elements.append(Paragraph(commentaire_client.strip(), styles["Normal"]))
        elements.append(Spacer(1, 12))

    doc.build(elements)
    st.success("✅ PDF généré avec succès !")

    st.download_button(
        label="📥 Télécharger le PDF",
        data=buffer.getvalue(),
        file_name="rapport_filtrage.pdf",
        mime="application/pdf"
    )

elif page == "Carte des clients":
    import streamlit as st
    import pandas as pd
    import folium
    from streamlit_folium import st_folium
    import unicodedata
    import html
    from fpdf import FPDF
    import tempfile
    import os

    st.title("🗺️ Carte des clients par région (clic sur une région)")

    coords_regions = {
        "Île-de-France": (48.8499, 2.6370),
        "Auvergne-Rhône-Alpes": (45.5, 4.5),
        "Nouvelle-Aquitaine": (45.7, 0.3),
        "Occitanie": (43.6, 2.2),
        "Provence-Alpes-Côte d'Azur": (43.9, 6.2),
        "Grand Est": (48.3, 5.3),
        "Bretagne": (48.2, -2.9),
        "Normandie": (49.2, 0.5),
        "Hauts-de-France": (50.3, 2.7),
        "Pays de la Loire": (47.5, -0.8),
        "Centre-Val de Loire": (47.7, 1.6),
        "Bourgogne-Franche-Comté": (47.1, 4.8),
        "Corse": (42.0396, 9.0129)
    }

    def normalize_str(s):
        if not isinstance(s, str):
            return ""
        s = s.replace('\xa0', ' ')
        s = s.strip().lower()
        s = unicodedata.normalize('NFD', s)
        s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
        return s

    def safe_val(v):
        if pd.isna(v):
            return "Non renseigné"
        return str(v).strip() if str(v).strip() else "Non renseigné"

    # Nettoyage et renommage des colonnes
    df.columns = (
        df.columns
        .str.strip()
        .str.replace("\xa0", " ", regex=False)
        .str.replace("\n", "", regex=False)
        .str.lower()
    )
    df = df.rename(columns={
        "nom du client": "nom",
        "provenance": "region",
        "montant reçu": "montant",
        "nom du fournisseur": "nom_fournisseur",
        "montant payé": "montant_paye",
        "sexe": "sexe",
        "âge": "age",
        "catégorie socio-professionnelle": "csp"
    })

    df["region_norm"] = df["region"].astype(str).apply(normalize_str)
    coords_regions_norm = {normalize_str(k): v for k, v in coords_regions.items()}
    norm_to_original = {normalize_str(k): k for k in coords_regions.keys()}

    df_clients = df[df["nom"].notna() & df["region_norm"].isin(coords_regions_norm.keys())].copy()
    df_fournisseurs = df[df["nom_fournisseur"].notna() & df["region_norm"].isin(coords_regions_norm.keys())].copy()

    if df_clients.empty:
        st.warning("Aucun client avec région valide.")
    else:
        region_counts = df_clients["region_norm"].value_counts().to_dict()
        m = folium.Map(location=[46.6, 2.5], zoom_start=6)

        region_id_map = {i: region for i, region in enumerate(coords_regions_norm.keys())}

        for i, (region_norm, (lat, lon)) in enumerate(coords_regions_norm.items()):
            count = region_counts.get(region_norm, 0)
            if count > 0:
                folium.CircleMarker(
                    location=(lat, lon),
                    radius=5 + count * 0.7,
                    color='blue',
                    fill=True,
                    fill_color='blue',
                    fill_opacity=0.6,
                    tooltip=f"{norm_to_original[region_norm]} : {count} client(s)",
                    popup=str(i)
                ).add_to(m)

        st.markdown("### 🖱️ Cliquez sur un cercle pour voir les clients")
        map_data = st_folium(m, width=700, height=500)

        selected_region = None
        if map_data and map_data.get("last_object_clicked_popup"):
            clicked_id_str = map_data["last_object_clicked_popup"]
            if clicked_id_str.isdigit():
                clicked_id = int(clicked_id_str)
                selected_region = region_id_map.get(clicked_id)

        st.subheader("📋 Détails des clients")

        if selected_region:
            selected_region_original = norm_to_original.get(selected_region, selected_region)
            st.markdown(f"### Région sélectionnée : **{selected_region_original}**")

            # Filtrage clients et fournisseurs par région sélectionnée
            filtered_clients = df_clients[df_clients["region_norm"] == selected_region]
            filtered_fournisseurs = df_fournisseurs[df_fournisseurs["region_norm"] == selected_region]

            # Calcul des metrics à afficher
            montant_recu_total = filtered_clients["montant"].sum()
            montant_paye_total = filtered_fournisseurs["montant_paye"].sum()
            solde = montant_recu_total - montant_paye_total
            nb_clients = filtered_clients["nom"].nunique()
            nb_fournisseurs = filtered_fournisseurs["nom_fournisseur"].nunique()

            # Affichage des metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("💰 Montant reçu", f"{montant_recu_total:.2f} EUR")
            col2.metric("💸 Montant payé", f"{montant_paye_total:.2f} EUR")
            col3.metric("📈 Solde", f"{solde:.2f} EUR")
            col4.metric("👥 Clients", f"{nb_clients}")
            col5.metric("🏭 Fournisseurs", f"{nb_fournisseurs}")

            st.write(f"Nombre de clients dans la région sélectionnée : {len(filtered_clients)}")

            for _, row in filtered_clients.iterrows():
                nom = html.escape(safe_val(row.get("nom")))
                provenance = html.escape(safe_val(row.get("region")))
                montant = row.get("montant", 0.0)
                sexe = html.escape(safe_val(row.get("sexe")))
                age = html.escape(safe_val(row.get("age")))
                csp = html.escape(safe_val(row.get("csp")))

                st.markdown(f"""
                <div style="border:1px solid #ddd; padding:10px; margin-bottom:15px; border-radius:5px;">
                    <h4>👤 {nom}</h4>
                    <p>📍 <b>Région :</b> {provenance}</p>
                    <p>💰 <b>Montant total reçu :</b> {montant:.2f} €</p>
                    <p>🧑 <b>Sexe :</b> {sexe} | <b>Âge :</b> {age}</p>
                    <p>🏷️ <b>CSP :</b> {csp}</p>
                </div>
                """, unsafe_allow_html=True)

            st.subheader("🗣️ Laissez un commentaire pour cette région")
            commentaire_client = st.text_area("Vos remarques à joindre au rapport PDF :", height=150)
            if st.button("🗑️ Supprimer le commentaire"):
                commentaire_client = ""
                st.experimental_rerun()

            st.markdown("### 📄 Export PDF")
            if st.button("Générer un PDF avec ces informations"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 14)
                # Titre + variables clés
                pdf.cell(0, 10, f"Clients de la région : {selected_region_original}".encode('latin-1', 'replace').decode('latin-1'), ln=True)
                pdf.ln(5)
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 8, f"Montant reçu total : {montant_recu_total:.2f} EUR", ln=True)
                pdf.cell(0, 8, f"Montant payé total : {montant_paye_total:.2f} EUR", ln=True)
                pdf.cell(0, 8, f"Solde : {solde:.2f} EUR", ln=True)
                pdf.cell(0, 8, f"Nombre de clients : {nb_clients}", ln=True)
                pdf.cell(0, 8, f"Nombre de fournisseurs : {nb_fournisseurs}", ln=True)
                pdf.ln(5)

                for _, row in filtered_clients.iterrows():
                    text_block = f"""
Nom : {safe_val(row.get("nom"))}
Région : {safe_val(row.get("region"))}
Montant reçu : {row.get("montant", 0.0):.2f} euros
Sexe : {safe_val(row.get("sexe"))}
Âge : {safe_val(row.get("age"))}
CSP : {safe_val(row.get("csp"))}
""".strip()
                    safe_text_block = text_block.encode('latin-1', 'replace').decode('latin-1')
                    pdf.ln(5)
                    pdf.multi_cell(0, 8, safe_text_block)

                if commentaire_client.strip():
                    pdf.ln(10)
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, "Commentaire de l'utilisateur :".encode('latin-1', 'replace').decode('latin-1'), ln=True)
                    pdf.set_font("Arial", "", 12)
                    for ligne in commentaire_client.strip().split('\n'):
                        safe_ligne = ligne.encode('latin-1', 'replace').decode('latin-1')
                        pdf.cell(0, 8, safe_ligne, ln=True)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    pdf.output(tmp_file.name)
                    st.success("PDF généré avec succès.")
                    with open(tmp_file.name, "rb") as f:
                        st.download_button("📥 Télécharger le PDF", f, file_name=f"{selected_region_original}.pdf")
                    os.unlink(tmp_file.name)

        else:
            st.info("Cliquez sur un cercle pour afficher les clients.")

elif page == "Veille concurrentielle":
    import streamlit as st
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    from bs4 import BeautifulSoup
    import re
    from fpdf import FPDF
    from io import BytesIO
    from datetime import datetime
    from urllib.parse import urljoin, urlparse
    import unidecode
    from langdetect import detect, LangDetectException
    from difflib import SequenceMatcher

    st.title("🔍 Veille concurrentielle automatisée")

    entreprise = st.text_input("Nom de l'entreprise")
    liens_sites = st.text_area("URLs des sites web (1 URL par ligne, max 5)")
    mots_cles_input = st.text_input("Mots-clés (séparés par des virgules)")

    mots_cles = [unidecode.unidecode(m.strip().lower()) for m in mots_cles_input.split(",") if m.strip()]
    MAX_PAGES = 5

    STOPWORDS = {
        "le","la","les","de","des","du","un","une","et","en","à","a","au","aux","pour","par","sur","dans","que","qui","ce","ces","se","ses","est","sont","d'","l'","avec","ou","où","mais","nous","vous","il","elle","ils","elles",
        "the","and","of","to","in","for","with","on","at","by","is","are","we","you","our","us","be","this","that","it","from","as","an"
    }

    def nettoyer_html(soup):
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form", "svg", "img", "meta", "link", "button", "input", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def extraire_phrases(texte):
        phrases = re.split(r'(?<=[.!?;:])\s+', texte)
        phrases = [p.strip() for p in phrases if 30 <= len(p.strip()) <= 600]
        return phrases

    def est_francais(texte):
        try:
            return detect(texte) == 'fr'
        except LangDetectException:
            return False

    def mots_cles_dans_phrase(phrase, mots):
        phrase_ascii = unidecode.unidecode(phrase.lower())
        return any(m in phrase_ascii for m in mots)

    def safe_pdf_text(txt):
        txt = txt.replace('\n', ' ').replace('\r', '')
        txt = unidecode.unidecode(txt)
        txt = re.sub(r'[^\x20-\x7E]+', ' ', txt)
        txt = re.sub(r'\s+', ' ', txt).strip()
        return txt

    def canonicalize_url(u):
        try:
            p = urlparse(u)
            scheme = p.scheme or "http"
            netloc = p.netloc
            path = p.path.rstrip('/')
            query = ('?' + p.query) if p.query else ''
            return f"{scheme}://{netloc}{path}{query}"
        except Exception:
            return u.split('#')[0]

    def crawler_site_playwright(url, max_pages=MAX_PAGES):
        pages_visited = set()
        to_visit = [url]
        textes = []

        domaine = urlparse(url).netloc

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36")

            while to_visit and len(pages_visited) < max_pages:
                current_url = to_visit.pop(0)
                canon_current = canonicalize_url(current_url)
                if canon_current in pages_visited:
                    continue
                try:
                    page = context.new_page()
                    page.goto(current_url, timeout=15000)
                    page.wait_for_timeout(7000)

                    content = page.content()
                    soup = BeautifulSoup(content, "html.parser")
                    texte = nettoyer_html(soup)
                    textes.append((current_url, texte))

                    pages_visited.add(canon_current)

                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        href_parsed = urlparse(href)
                        if href_parsed.scheme in ['http', 'https']:
                            lien_complet = href
                        else:
                            lien_complet = urljoin(current_url, href)

                        try:
                            domaine_lien = urlparse(lien_complet).netloc
                        except Exception:
                            domaine_lien = ''
                        if domaine_lien == domaine:
                            canon_link = canonicalize_url(lien_complet)
                            already_in_to_visit = any(canonicalize_url(t) == canon_link for t in to_visit)
                            if canon_link not in pages_visited and not already_in_to_visit:
                                to_visit.append(lien_complet)
                    page.close()
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue

            browser.close()
        return textes

    def normalize_for_dedup(text):
        s = unidecode.unidecode(text.lower())
        s = re.sub(r'http\S+', ' ', s)
        s = re.sub(r'\d+', ' ', s)
        s = re.sub(r'[^\w\s]', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        tokens = [t for t in s.split() if t not in STOPWORDS and len(t) > 2]
        norm_str = ' '.join(tokens)
        return tokens, norm_str

    def is_similar(passage, existing_passages, token_thresh=0.55, seq_thresh=0.78):
        tokens_a, norm_a = normalize_for_dedup(passage)
        set_a = set(tokens_a)
        if not set_a:
            return False

        for _, existing in existing_passages:
            tokens_b, norm_b = normalize_for_dedup(existing)
            set_b = set(tokens_b)
            if not set_b:
                continue

            inter = set_a.intersection(set_b)
            min_len = min(len(set_a), len(set_b))
            if min_len > 0:
                overlap_ratio = len(inter) / min_len
                if overlap_ratio >= token_thresh:
                    return True

            if norm_a and norm_b:
                seq_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()
                if seq_ratio >= seq_thresh:
                    return True

            if norm_a and norm_b:
                if norm_a in norm_b or norm_b in norm_a:
                    if len(norm_a) >= 20 and len(norm_b) >= 20:
                        return True

        return False

    if st.button("Générer le rapport PDF"):
        urls = [u.strip() for u in liens_sites.split("\n") if u.strip()]
        if not entreprise or not urls or not mots_cles:
            st.error("Merci de renseigner tous les champs (nom, URLs, mots-clés).")
        elif len(urls) > 5:
            st.error("Merci de ne pas saisir plus de 5 URLs.")
        else:
            with st.spinner("Extraction et analyse en cours... cela peut prendre quelques secondes..."):
                all_pages_textes = []
                for url in urls:
                    st.write(f"Analyse du site : {url}")
                    try:
                        pages_textes = crawler_site_playwright(url, MAX_PAGES)
                        all_pages_textes.extend(pages_textes)
                    except Exception as e:
                        st.warning(f"Erreur lors du crawl de {url} : {e}")

                st.write(f"Nombre total de pages analysées : {len(all_pages_textes)}")

                toutes_phrases = []
                for url_page, texte in all_pages_textes:
                    phrases = extraire_phrases(texte)
                    for p in phrases:
                        if mots_cles_dans_phrase(p, mots_cles) and est_francais(p):
                            toutes_phrases.append((url_page, p))

                unique_phrases = []
                seen_exact = set()
                for url_page, passage in toutes_phrases:
                    if passage in seen_exact:
                        continue
                    if is_similar(passage, unique_phrases, token_thresh=0.55, seq_thresh=0.78):
                        continue
                    seen_exact.add(passage)
                    unique_phrases.append((url_page, passage))

                toutes_phrases = unique_phrases
                st.write(f"Passages pertinents après suppression des doublons : {len(toutes_phrases)}")

            if toutes_phrases:
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()

                # En-tête
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "Rapport de veille concurrentielle", ln=True, align="C")
                pdf.ln(8)

                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, f"Entreprise : {entreprise}", ln=True)
                pdf.cell(0, 8, f"Liens : {', '.join(urls)}", ln=True)
                pdf.cell(0, 8, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)
                pdf.ln(10)

                # Corps du document
                pdf.set_font("Arial", "", 12)
                largeur_cell = 180
                interligne = 7

                for idx, (url_page, passage) in enumerate(toutes_phrases[:30], 1):
                    pdf.set_fill_color(240, 240, 240)
                    x_start = pdf.get_x()
                    y_start = pdf.get_y()

                    texte = safe_pdf_text(passage)

                    # Vérifier hauteur avant impression (si besoin d’une nouvelle page)
                    temp_pdf = FPDF()
                    temp_pdf.add_page()
                    temp_pdf.set_font("Arial", "", 12)
                    temp_pdf.multi_cell(largeur_cell, interligne, f"Passage {idx}:\n{texte}")
                    hauteur_necessaire = temp_pdf.get_y()
                    hauteur_totale = hauteur_necessaire + 14  # marge + source

                    if pdf.get_y() + hauteur_totale > pdf.page_break_trigger:
                        pdf.add_page()
                        x_start = pdf.get_x()
                        y_start = pdf.get_y()

                    # Impression du passage
                    pdf.multi_cell(largeur_cell, interligne, f"Passage {idx}:\n{texte}", fill=True)
                    y_end = pdf.get_y()

                    # Bordure autour du passage
                    pdf.rect(x_start - 1, y_start - 1, largeur_cell + 2, y_end - y_start + 2)

                    # Source du passage
                    pdf.ln(2)
                    pdf.set_text_color(100, 100, 100)
                    pdf.set_font("Arial", "I", 10)
                    url_court = url_page if len(url_page) <= 70 else url_page[:67] + "..."
                    pdf.cell(largeur_cell, 6, f"Source : {url_court}", ln=True)

                    # Reset style
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("Arial", "", 12)
                    pdf.ln(6)

                buffer = BytesIO()
                pdf.output(buffer)
                buffer.seek(0)

                st.success("PDF généré avec succès.")
                st.download_button(
                    label="📥 Télécharger le rapport PDF",
                    data=buffer,
                    file_name=f"veille_concurrentielle_{entreprise}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
            else:
                st.warning("Aucun passage pertinent trouvé avec ces mots-clés.")
