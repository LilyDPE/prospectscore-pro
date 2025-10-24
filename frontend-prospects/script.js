// Fonction pour afficher les détails de détection
function getIndicesBadge(details) {
    if (!details) return '<span class="text-muted">-</span>';
    
    const items = details.split(' • ');
    let html = '<div style="font-size: 11px; line-height: 1.4;">';
    items.forEach(item => {
        html += `<div style="margin-bottom: 2px;">• ${item}</div>`;
    });
    html += '</div>';
    return html;
}

// Ajouter dans displayProspects après la colonne propriétaire
// Cette fonction sera intégrée dans l'HTML principal
