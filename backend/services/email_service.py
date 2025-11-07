"""
Service d'envoi d'emails pour les commerciaux
Support SMTP ou services comme SendGrid, Mailgun, etc.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from datetime import datetime

class EmailService:
    """Service d'envoi d'emails"""

    def __init__(self):
        # Configuration SMTP depuis variables d'environnement
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@2a-immobilier.com")
        self.from_name = os.getenv("FROM_NAME", "ProspectScore Pro")

    def send_prospects_to_commercial(
        self,
        commercial_email: str,
        commercial_name: str,
        prospects: List[Dict[str, Any]]
    ) -> bool:
        """
        Envoyer une liste de prospects par email au commercial

        Args:
            commercial_email: Email du commercial
            commercial_name: Nom du commercial
            prospects: Liste des prospects assignés

        Returns:
            True si envoi réussi, False sinon
        """
        try:
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🎯 {len(prospects)} nouveaux prospects vous ont été assignés"
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = commercial_email

            # Construire le corps de l'email
            html_content = self._build_prospects_email_html(commercial_name, prospects)
            text_content = self._build_prospects_email_text(commercial_name, prospects)

            # Attacher les parties
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')

            msg.attach(part1)
            msg.attach(part2)

            # Envoyer via SMTP
            if self.smtp_user and self.smtp_password:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
                return True
            else:
                print("⚠️  Configuration SMTP manquante - Email non envoyé")
                print(f"   Pour activer les emails, configurez SMTP_USER et SMTP_PASSWORD")
                return False

        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            return False

    def _build_prospects_email_html(self, commercial_name: str, prospects: List[Dict]) -> str:
        """Construire l'email HTML avec les prospects"""

        # Header
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #04264b 0%, #0a4a8a 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}
                .content {{
                    background: #f9f9f9;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                }}
                .prospect {{
                    background: white;
                    padding: 20px;
                    margin: 15px 0;
                    border-radius: 8px;
                    border-left: 4px solid #b4e434;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .prospect-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 15px;
                }}
                .adresse {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #04264b;
                }}
                .score {{
                    background: #b4e434;
                    color: #04264b;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 16px;
                }}
                .score.haute {{
                    background: #4CAF50;
                    color: white;
                }}
                .score.moyenne {{
                    background: #FFC107;
                    color: #333;
                }}
                .details {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 10px;
                    margin-top: 10px;
                    font-size: 14px;
                }}
                .detail-item {{
                    padding: 5px 0;
                }}
                .detail-label {{
                    color: #666;
                    font-weight: 500;
                }}
                .detail-value {{
                    color: #333;
                    font-weight: 600;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding: 20px;
                    color: #666;
                    font-size: 12px;
                }}
                .cta {{
                    background: #04264b;
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 5px;
                    display: inline-block;
                    margin: 20px 0;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎯 Nouveaux Prospects</h1>
                <p style="margin: 10px 0 0 0; font-size: 18px;">Bonjour {commercial_name},</p>
            </div>

            <div class="content">
                <p style="font-size: 16px; margin-bottom: 20px;">
                    <strong>{len(prospects)} nouveaux prospects</strong> à forte probabilité de vente
                    vous ont été assignés dans vos zones.
                </p>
        """

        # Prospects
        for i, prospect in enumerate(prospects, 1):
            score = prospect.get('propensity_score', 0)
            priorite = prospect.get('priorite', 'MOYENNE').lower()

            score_class = 'haute' if score >= 80 else 'moyenne' if score >= 60 else ''

            html += f"""
                <div class="prospect">
                    <div class="prospect-header">
                        <div class="adresse">
                            #{i} - {prospect.get('adresse', 'Adresse non disponible')}
                        </div>
                        <div class="score {score_class}">
                            Score: {score}/100
                        </div>
                    </div>

                    <div class="details">
                        <div class="detail-item">
                            <span class="detail-label">📍 Code postal:</span>
                            <span class="detail-value">{prospect.get('code_postal', 'N/A')}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">🏘️ Commune:</span>
                            <span class="detail-value">{prospect.get('commune', 'N/A')}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">🏠 Type:</span>
                            <span class="detail-value">{prospect.get('type_local', 'N/A')}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">📏 Surface:</span>
                            <span class="detail-value">{prospect.get('surface_reelle', 'N/A')} m²</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">🛏️ Pièces:</span>
                            <span class="detail-value">{prospect.get('nombre_pieces', 'N/A')}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">💰 Dernier prix:</span>
                            <span class="detail-value">{prospect.get('last_price', 'N/A')} €</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">📊 Zone:</span>
                            <span class="detail-value">{prospect.get('zone_type', 'N/A')}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">⚡ Priorité:</span>
                            <span class="detail-value">{priorite.upper()}</span>
                        </div>
                    </div>
                </div>
            """

        # Footer
        html += f"""
                <div style="text-align: center;">
                    <a href="https://score.2a-immobilier.com/commercial" class="cta">
                        📱 Accéder à mes prospects
                    </a>
                </div>

                <p style="margin-top: 30px; padding: 15px; background: #e3f2fd; border-radius: 5px;">
                    💡 <strong>Conseil:</strong> Priorisez les prospects avec un score ≥ 80 pour maximiser
                    vos chances de conversion. Ces biens ont la plus forte probabilité de vente dans les 6 mois.
                </p>
            </div>

            <div class="footer">
                <p>
                    <strong>ProspectScore Pro</strong> - 2A Immobilier<br>
                    Système de scoring intelligent de vendeurs potentiels<br>
                    Envoyé le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
                </p>
                <p style="margin-top: 10px; font-size: 11px; color: #999;">
                    Cet email a été généré automatiquement. Pour toute question, contactez votre administrateur.
                </p>
            </div>
        </body>
        </html>
        """

        return html

    def _build_prospects_email_text(self, commercial_name: str, prospects: List[Dict]) -> str:
        """Construire l'email en texte brut"""

        text = f"""
🎯 NOUVEAUX PROSPECTS - ProspectScore Pro
==========================================

Bonjour {commercial_name},

{len(prospects)} nouveaux prospects à forte probabilité de vente vous ont été assignés dans vos zones.

"""

        for i, prospect in enumerate(prospects, 1):
            text += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROSPECT #{i} - Score: {prospect.get('propensity_score', 0)}/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 Adresse: {prospect.get('adresse', 'N/A')}
🏘️ Code postal: {prospect.get('code_postal', 'N/A')} - {prospect.get('commune', 'N/A')}
🏠 Type: {prospect.get('type_local', 'N/A')}
📏 Surface: {prospect.get('surface_reelle', 'N/A')} m²
🛏️ Pièces: {prospect.get('nombre_pieces', 'N/A')}
💰 Dernier prix: {prospect.get('last_price', 'N/A')} €
📊 Zone: {prospect.get('zone_type', 'N/A')}
⚡ Priorité: {prospect.get('priorite', 'MOYENNE')}

"""

        text += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 CONSEIL: Priorisez les prospects avec un score ≥ 80 pour maximiser vos chances de conversion.

📱 Accédez à votre interface : https://score.2a-immobilier.com/commercial

--
ProspectScore Pro - 2A Immobilier
Envoyé le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
        """

        return text

# Instance globale
email_service = EmailService()
