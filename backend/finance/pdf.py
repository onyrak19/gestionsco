"""PDF des finances : reçus, cartes d'écolage, fiches de paie, états et bilans.

Comme `school/pdf.py`, ce module ne touche pas à la base de données : il reçoit des
dictionnaires préparés par les vues et retourne les octets du PDF.
"""
import math
from datetime import date, datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, A5, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from school.pdf import (
    ACCENT, CLAIR, GRIS, PRIMAIRE, TRAIT, _ajuster, _en_tete, _nouveau, date_fr,
)

from .outils import montant_fr

VERT = colors.HexColor('#15803d')
VERT_CLAIR = colors.HexColor('#dcfce7')
ROUGE = colors.HexColor('#b91c1c')
ROUGE_CLAIR = colors.HexColor('#fee2e2')
GRIS_CLAIR = colors.HexColor('#f1f5f9')
TEXTE = colors.HexColor('#334155')


def _date(valeur, court=True):
    if isinstance(valeur, str) and valeur:
        try:
            valeur = date.fromisoformat(valeur[:10])
        except ValueError:
            return valeur
    if isinstance(valeur, datetime):
        valeur = valeur.date()
    return date_fr(valeur, court=court) if valeur else ''


def _filigrane(c, texte, largeur, hauteur):
    c.saveState()
    c.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.18))
    c.setFont('Helvetica-Bold', 60)
    c.translate(largeur / 2, hauteur / 2)
    c.rotate(30)
    c.drawCentredString(0, 0, texte)
    c.restoreState()


def _ligne_info(c, x, y, libelle, valeur, largeur, taille=9):
    c.setFillColor(GRIS)
    c.setFont('Helvetica', taille - 1)
    c.drawString(x, y, libelle)
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', taille)
    c.drawString(x + 27 * mm, y, _ajuster(valeur, 'Helvetica-Bold', taille, largeur - 27 * mm))


# ---------------------------------------------------------------------------
# Reçu de paiement d'élève (A5 paysage)
# ---------------------------------------------------------------------------
def recu_pdf(recu, etab, devise=''):
    """recu : numero, date, eleve, matricule, classe, annee, type_libelle, lignes [{libelle, montant}],
    total, mode_libelle, reference, observation, caissier, annule, motif_annulation."""
    page = landscape(A5)
    buf, c = _nouveau(page)
    W, H = page
    _en_tete(c, etab, W, H, hauteur=24 * mm)

    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 15)
    c.drawString(14 * mm, H - 36 * mm, 'REÇU DE PAIEMENT')
    c.setFont('Helvetica-Bold', 11)
    c.drawRightString(W - 14 * mm, H - 36 * mm, f"N° {recu['numero']}")
    c.setFillColor(GRIS)
    c.setFont('Helvetica', 9)
    c.drawRightString(W - 14 * mm, H - 41.5 * mm, f"Date : {_date(recu['date'])}")

    y = H - 49 * mm
    largeur_col = (W - 28 * mm) / 2
    infos = [('Élève', recu['eleve']), ('Matricule', recu.get('matricule') or '—'),
             ('Classe', recu.get('classe') or '—'), ('Année scolaire', recu.get('annee') or '—')]
    for k, (lib, val) in enumerate(infos):
        _ligne_info(c, 14 * mm + (k % 2) * largeur_col, y - (k // 2) * 5.5 * mm, lib, val, largeur_col - 4 * mm)
    y -= 15 * mm

    lignes = recu['lignes']
    if len(lignes) > 6:                         # beaucoup de mois : une seule ligne récapitulative
        libelles = ', '.join(l['libelle'].replace('Écolage ', '') for l in lignes)
        lignes = [{'libelle': f"{recu['type_libelle']} — {len(lignes)} mois : {libelles}", 'montant': recu['total']}]
    style = ParagraphStyle('cellule', fontName='Helvetica', fontSize=9, leading=11, textColor=TEXTE)
    donnees = [['Désignation', 'Montant']] + [
        [Paragraph(l['libelle'], style), montant_fr(l['montant'], devise)] for l in lignes]
    donnees.append(['TOTAL PAYÉ', montant_fr(recu['total'], devise)])
    table = Table(donnees, colWidths=[W - 28 * mm - 45 * mm, 45 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMAIRE), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('BACKGROUND', (0, -1), (-1, -1), CLAIR),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (-1, -2), 0.4, TRAIT), ('BOX', (0, 0), (-1, -1), 0.6, TRAIT),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    _, hauteur_table = table.wrapOn(c, W - 28 * mm, y)
    table.drawOn(c, 14 * mm, y - hauteur_table)
    y -= hauteur_table + 7 * mm

    c.setFillColor(TEXTE)
    c.setFont('Helvetica', 8.5)
    c.drawString(14 * mm, y, f"Mode de paiement : {recu['mode_libelle']}"
                 + (f"   ·   Référence : {recu['reference']}" if recu.get('reference') else ''))
    if recu.get('observation'):
        y -= 4.5 * mm
        c.drawString(14 * mm, y, _ajuster(f"Observation : {recu['observation']}", 'Helvetica', 8.5, W - 28 * mm))

    c.setFillColor(GRIS)
    c.setFont('Helvetica', 8)
    c.drawString(14 * mm, 14 * mm, f"Reçu par : {recu.get('caissier') or '—'}")
    c.drawRightString(W - 14 * mm, 20 * mm, 'Cachet et signature')
    c.setStrokeColor(TRAIT)
    c.line(W - 64 * mm, 18 * mm, W - 14 * mm, 18 * mm)
    c.setFont('Helvetica-Oblique', 7)
    c.drawCentredString(W / 2, 8 * mm, "Ce reçu fait foi de paiement. Conservez-le précieusement.")

    if recu.get('annule'):
        _filigrane(c, 'ANNULÉ', W, H)
        c.setFillColor(ROUGE)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawString(14 * mm, 24 * mm, _ajuster(f"Annulé : {recu.get('motif_annulation') or ''}", 'Helvetica-Bold', 8.5, W - 90 * mm))
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Cartes d'écolage (2 par page A4)
# ---------------------------------------------------------------------------
def cartes_ecolage_pdf(cartes, etab, devise=''):
    buf, c = _nouveau(A4)
    W, H = A4
    if not cartes:
        c.setFont('Helvetica', 12)
        c.setFillColor(GRIS)
        c.drawCentredString(W / 2, H / 2, "Aucune carte d'écolage à imprimer")
    cw, ch = 190 * mm, 132 * mm
    x = (W - cw) / 2
    for i, carte in enumerate(cartes):
        pos = i % 2
        if pos == 0 and i > 0:
            c.showPage()
        y = H - 8 * mm - (pos + 1) * ch - pos * 8 * mm
        _carte_ecolage(c, x, y, cw, ch, carte, etab, devise)
    c.save()
    return buf.getvalue()


def _carte_ecolage(c, x, y, w, h, carte, etab, devise):
    c.saveState()
    chemin = c.beginPath()
    chemin.roundRect(x, y, w, h, 3 * mm)
    c.clipPath(chemin, stroke=0, fill=0)
    c.setFillColor(colors.white)
    c.rect(x, y, w, h, stroke=0, fill=1)
    c.setFillColor(PRIMAIRE)
    c.rect(x, y + h - 15 * mm, w, 15 * mm, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.rect(x, y + h - 16 * mm, w, 1 * mm, stroke=0, fill=1)
    c.restoreState()
    c.setStrokeColor(TRAIT)
    c.setLineWidth(0.7)
    c.roundRect(x, y, w, h, 3 * mm, stroke=1, fill=0)

    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(x + 6 * mm, y + h - 7 * mm, _ajuster(etab['nom'], 'Helvetica-Bold', 12, w - 80 * mm))
    c.setFont('Helvetica', 8)
    c.drawString(x + 6 * mm, y + h - 12 * mm, _ajuster(
        ' · '.join(v for v in (etab.get('ville'), etab.get('telephone')) if v), 'Helvetica', 8, w - 80 * mm))
    c.setFont('Helvetica-Bold', 11)
    c.drawRightString(x + w - 6 * mm, y + h - 7 * mm, "CARTE D'ÉCOLAGE")
    c.setFont('Helvetica', 8.5)
    c.drawRightString(x + w - 6 * mm, y + h - 12 * mm, f"Année scolaire {carte['annee']}")

    # Identité
    iy = y + h - 24 * mm
    moitie = (w - 12 * mm) / 2
    _ligne_info(c, x + 6 * mm, iy, 'Élève', f"{(carte['nom'] or '').upper()} {carte['prenom']}".strip(), moitie)
    _ligne_info(c, x + 6 * mm, iy - 5.5 * mm, 'Classe', carte['classe'], moitie)
    _ligne_info(c, x + 6 * mm + moitie, iy, 'Matricule', carte.get('matricule') or '—', moitie)
    parent = ' · '.join(v for v in (carte.get('parent_nom'), carte.get('parent_mobile')) if v) or '—'
    _ligne_info(c, x + 6 * mm + moitie, iy - 5.5 * mm, 'Parent / tuteur', parent, moitie)

    # Droit d'inscription
    droit = carte.get('droit') or {}
    dy = iy - 13 * mm
    c.setFillColor(GRIS_CLAIR)
    c.rect(x + 6 * mm, dy - 2 * mm, w - 12 * mm, 7 * mm, stroke=0, fill=1)
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(x + 8 * mm, dy, "Droit d'inscription")
    if droit.get('montant') is None:
        c.setFillColor(GRIS)
        c.setFont('Helvetica', 8.5)
        c.drawString(x + 50 * mm, dy, 'Non défini')
    else:
        c.setFillColor(TEXTE)
        c.setFont('Helvetica', 8.5)
        c.drawString(x + 50 * mm, dy, montant_fr(droit['montant'], devise))
        c.setFont('Helvetica-Bold', 8.5)
        if droit.get('paye'):
            c.setFillColor(VERT)
            c.drawString(x + 85 * mm, dy, f"PAYÉ le {_date(droit.get('date_paiement'))}  (reçu {droit.get('numero_recu')})")
        else:
            c.setFillColor(ROUGE)
            c.drawString(x + 85 * mm, dy, 'NON PAYÉ')

    # Grille des mois
    mois = carte.get('mois') or []
    colonnes = 4
    lignes = max(1, math.ceil(len(mois) / colonnes))
    haut_grille = dy - 6 * mm
    bas_grille = y + 16 * mm
    ch_cellule = min(21 * mm, (haut_grille - bas_grille) / lignes)
    cw_cellule = (w - 12 * mm) / colonnes
    for k, m in enumerate(mois):
        cx = x + 6 * mm + (k % colonnes) * cw_cellule
        cy = haut_grille - (k // colonnes + 1) * ch_cellule
        statut = m['statut']
        fond = VERT_CLAIR if statut == 'paye' else (ROUGE_CLAIR if statut == 'impaye' else GRIS_CLAIR)
        c.setFillColor(fond)
        c.setStrokeColor(TRAIT)
        c.setLineWidth(0.5)
        c.rect(cx + 0.6 * mm, cy + 0.6 * mm, cw_cellule - 1.2 * mm, ch_cellule - 1.2 * mm, stroke=1, fill=1)
        c.setFillColor(PRIMAIRE)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(cx + 3 * mm, cy + ch_cellule - 6 * mm, m['libelle'])
        if statut == 'paye':
            c.setFillColor(VERT)
            c.setFont('Helvetica-Bold', 9)
            c.drawString(cx + 3 * mm, cy + ch_cellule - 11 * mm, 'PAYÉ')
            c.setFont('Helvetica', 7)
            c.setFillColor(TEXTE)
            c.drawString(cx + 3 * mm, cy + ch_cellule - 14.8 * mm, _ajuster(
                f"le {_date(m.get('date_paiement'))} · {montant_fr(m['montant'], devise)}", 'Helvetica', 7, cw_cellule - 5 * mm))
            if ch_cellule > 19 * mm:
                c.drawString(cx + 3 * mm, cy + ch_cellule - 18 * mm, f"reçu {m.get('numero_recu') or ''}")
        else:
            c.setFillColor(ROUGE if statut == 'impaye' else GRIS)
            c.setFont('Helvetica-Bold', 9)
            c.drawString(cx + 3 * mm, cy + ch_cellule - 11 * mm, 'NON PAYÉ')
            if m.get('montant') is not None:
                c.setFont('Helvetica', 7)
                c.setFillColor(TEXTE)
                c.drawString(cx + 3 * mm, cy + ch_cellule - 14.8 * mm, f"à payer : {montant_fr(m['montant'], devise)}")

    # Pied
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(x + 6 * mm, y + 9 * mm, f"Total payé : {montant_fr(carte.get('total_paye'), devise) or '0'}")
    du = carte.get('du_a_ce_jour') or 0
    c.setFillColor(ROUGE if du > 0 else VERT)
    c.drawString(x + 6 * mm, y + 4.5 * mm, f"Reste dû à ce jour : {montant_fr(du, devise) or '0'}")
    c.setFillColor(GRIS)
    c.setFont('Helvetica', 7.5)
    c.drawRightString(x + w - 6 * mm, y + 4.5 * mm, f"Édité le {_date(carte.get('edite_le'))}   ·   Cachet de l'établissement")


# ---------------------------------------------------------------------------
# Fiche de paie (A5 paysage)
# ---------------------------------------------------------------------------
def fiche_paie_pdf(paie, etab, devise=''):
    """paie : numero, date, employe, poste, mois [libellés], salaire_mensuel, brut, retenue_avances,
    autres_retenues, motif_retenues, net, mode_libelle, exceptionnel, motif_exceptionnel, annule..."""
    page = landscape(A5)
    buf, c = _nouveau(page)
    W, H = page
    _en_tete(c, etab, W, H, hauteur=24 * mm)
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 15)
    c.drawString(14 * mm, H - 36 * mm, 'FICHE DE PAIE')
    c.setFont('Helvetica-Bold', 11)
    c.drawRightString(W - 14 * mm, H - 36 * mm, f"N° {paie['numero']}")
    c.setFillColor(GRIS)
    c.setFont('Helvetica', 9)
    c.drawRightString(W - 14 * mm, H - 41.5 * mm, f"Payée le {_date(paie['date'])}")

    y = H - 49 * mm
    moitie = (W - 28 * mm) / 2
    _ligne_info(c, 14 * mm, y, 'Employé', paie['employe'], moitie - 4 * mm)
    _ligne_info(c, 14 * mm + moitie, y, 'Poste', paie.get('poste') or '—', moitie - 4 * mm)
    periode = ', '.join(paie.get('mois') or []) or '—'
    c.setFillColor(GRIS)
    c.setFont('Helvetica', 8)
    c.drawString(14 * mm, y - 5.5 * mm, 'Période')
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(41 * mm, y - 5.5 * mm, _ajuster(periode, 'Helvetica-Bold', 9, W - 55 * mm))
    y -= 12 * mm

    style = ParagraphStyle('cellule', fontName='Helvetica', fontSize=9, leading=11, textColor=TEXTE)
    libelle_brut = (f"Montant exceptionnel — {paie['motif_exceptionnel']}" if paie.get('exceptionnel')
                    else f"Salaire : {montant_fr(paie.get('salaire_mensuel'), devise)} × {len(paie.get('mois') or [])} mois")
    donnees = [['Désignation', 'Montant'], [Paragraph(libelle_brut, style), montant_fr(paie['brut'], devise)]]
    if paie.get('retenue_avances'):
        donnees.append([Paragraph('Retenue sur avance(s) de salaire', style), '− ' + montant_fr(paie['retenue_avances'], devise)])
    if paie.get('autres_retenues'):
        donnees.append([Paragraph(f"Retenue : {paie.get('motif_retenues') or 'autre'}", style),
                        '− ' + montant_fr(paie['autres_retenues'], devise)])
    donnees.append(['NET PAYÉ', montant_fr(paie['net'], devise)])
    table = Table(donnees, colWidths=[W - 28 * mm - 45 * mm, 45 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMAIRE), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('BACKGROUND', (0, -1), (-1, -1), CLAIR),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (-1, -2), 0.4, TRAIT), ('BOX', (0, 0), (-1, -1), 0.6, TRAIT),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    _, hauteur_table = table.wrapOn(c, W - 28 * mm, y)
    table.drawOn(c, 14 * mm, y - hauteur_table)
    y -= hauteur_table + 6 * mm
    c.setFillColor(TEXTE)
    c.setFont('Helvetica', 8.5)
    c.drawString(14 * mm, y, f"Mode de paiement : {paie['mode_libelle']}")

    c.setFillColor(GRIS)
    c.setFont('Helvetica', 8)
    c.drawString(14 * mm, 20 * mm, "Signature de l'employé")
    c.line(14 * mm, 18 * mm, 64 * mm, 18 * mm)
    c.drawRightString(W - 14 * mm, 20 * mm, 'Cachet et signature de la direction')
    c.line(W - 74 * mm, 18 * mm, W - 14 * mm, 18 * mm)
    if paie.get('annule'):
        _filigrane(c, 'ANNULÉE', W, H)
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Documents tabulaires (impayés, bilan, journal de caisse...)
# ---------------------------------------------------------------------------
def document_pdf(etab, titre, sous_titre, blocs, paysage=False):
    """blocs : ('titre', texte) | ('texte', texte) | ('paires', [(libellé, valeur)])
    | ('tableau', entetes, lignes, largeurs_relatives|None, alignements|None, ligne_totaux|None)"""
    page = landscape(A4) if paysage else A4
    W, H = page
    buf = BytesIO()

    def entete(c, doc):
        c.saveState()
        c.setFillColor(PRIMAIRE)
        c.rect(0, H - 17 * mm, W, 17 * mm, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(0, H - 18 * mm, W, 1 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(14 * mm, H - 9 * mm, _ajuster(etab['nom'], 'Helvetica-Bold', 12, W - 100 * mm))
        c.setFont('Helvetica', 8)
        c.drawString(14 * mm, H - 14 * mm, _ajuster(
            ' · '.join(v for v in (etab.get('adresse'), etab.get('ville'), etab.get('telephone')) if v),
            'Helvetica', 8, W - 100 * mm))
        c.setFont('Helvetica-Bold', 11)
        c.drawRightString(W - 14 * mm, H - 10 * mm, titre)
        c.setFillColor(GRIS)
        c.setFont('Helvetica', 7.5)
        c.drawString(14 * mm, 8 * mm, f"Édité le {_date(date.today())}")
        c.drawRightString(W - 14 * mm, 8 * mm, f"Page {doc.page}")
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=24 * mm, bottomMargin=16 * mm, title=titre)
    largeur_utile = W - 28 * mm
    h1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=14, textColor=PRIMAIRE, spaceAfter=2)
    h2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=10.5, textColor=PRIMAIRE, spaceBefore=8, spaceAfter=4)
    normal = ParagraphStyle('n', fontName='Helvetica', fontSize=9, textColor=TEXTE, leading=12)
    cellule = ParagraphStyle('c', fontName='Helvetica', fontSize=8, textColor=TEXTE, leading=10)
    droite = ParagraphStyle('d', parent=cellule, alignment=TA_RIGHT)

    histoire = [Paragraph(titre, h1)]
    if sous_titre:
        histoire.append(Paragraph(sous_titre, normal))
    histoire.append(Spacer(1, 4 * mm))

    for bloc in blocs:
        genre = bloc[0]
        if genre == 'titre':
            histoire.append(Paragraph(bloc[1], h2))
        elif genre == 'texte':
            histoire.append(Paragraph(bloc[1], normal))
        elif genre == 'paires':
            t = Table([[Paragraph(a, cellule), Paragraph(f"<b>{b}</b>", droite)] for a, b in bloc[1]],
                      colWidths=[largeur_utile * 0.6, largeur_utile * 0.4])
            t.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 0.3, TRAIT), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
            histoire.append(t)
        elif genre == 'tableau':
            _, entetes, lignes, largeurs, aligns, totaux = (list(bloc) + [None] * 6)[:6]
            if not lignes:
                histoire.append(Paragraph('Aucune donnée pour cette sélection.', normal))
                continue
            largeurs = largeurs or [1] * len(entetes)
            somme = float(sum(largeurs))
            cols = [largeur_utile * l / somme for l in largeurs]
            aligns = aligns or ['L'] * len(entetes)

            def cell(valeur, a):
                return Paragraph(str(valeur if valeur is not None else ''), droite if a == 'R' else cellule)
            donnees = [[Paragraph(f"<b>{e}</b>", droite if a == 'R' else cellule) for e, a in zip(entetes, aligns)]]
            donnees += [[cell(v, a) for v, a in zip(ligne, aligns)] for ligne in lignes]
            if totaux:
                donnees.append([Paragraph(f"<b>{v}</b>" if v != '' else '', droite if a == 'R' else cellule)
                                for v, a in zip(totaux, aligns)])
            t = Table(donnees, colWidths=cols, repeatRows=1)
            style = [
                ('BACKGROUND', (0, 0), (-1, 0), CLAIR), ('LINEBELOW', (0, 0), (-1, 0), 0.8, PRIMAIRE),
                ('LINEBELOW', (0, 1), (-1, -1), 0.3, TRAIT), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
            ]
            if totaux:
                style += [('BACKGROUND', (0, -1), (-1, -1), CLAIR), ('LINEABOVE', (0, -1), (-1, -1), 0.8, PRIMAIRE)]
            t.setStyle(TableStyle(style))
            histoire.append(t)
        histoire.append(Spacer(1, 3 * mm))

    doc.build(histoire, onFirstPage=entete, onLaterPages=entete)
    return buf.getvalue()
