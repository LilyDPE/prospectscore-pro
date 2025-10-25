
// ======================================
// SYSTÈME DE NOTES ET COLLABORATION
// ======================================

let currentUser = localStorage.getItem('commercial_name');
if (!currentUser) {
    currentUser = prompt("👤 Votre nom (pour le tracking) :") || "Commercial";
    localStorage.setItem('commercial_name', currentUser);
}

// Mettre à jour le nom du commercial dans l'interface
document.addEventListener('DOMContentLoaded', () => {
    const userBadge = document.createElement('div');
    userBadge.style.cssText = 'position:fixed;top:20px;right:20px;background:white;padding:10px 20px;border-radius:20px;box-shadow:0 2px 10px rgba(0,0,0,0.1);z-index:1000;';
    userBadge.innerHTML = `👤 <strong>${currentUser}</strong> <button onclick="changeUser()" style="border:none;background:none;cursor:pointer;margin-left:10px;">✏️</button>`;
    document.body.appendChild(userBadge);
});

function changeUser() {
    const newName = prompt("Nouveau nom :", currentUser);
    if (newName) {
        currentUser = newName;
        localStorage.setItem('commercial_name', newName);
        location.reload();
    }
}

// Tracker automatiquement les vues
function trackView(transactionId) {
    fetch(`${API_URL}/api/collaboration/track-consultation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            transaction_id: transactionId,
            commercial: currentUser,
            action: 'vue'
        })
    }).catch(e => console.log('Track error:', e));
}

// Badges collaboratifs
function getCollaborationBadges(prospect) {
    let badges = '';
    
    // Badge si d'autres ont vu
    if (prospect.nb_commerciaux_vus > 1) {
        badges += `<span style="background:#9E9E9E;color:white;padding:3px 8px;border-radius:12px;font-size:10px;margin-left:5px;" title="Vu par ${prospect.nb_commerciaux_vus} commerciaux">👥 ${prospect.nb_commerciaux_vus}</span>`;
    }
    
    // Badge si quelqu'un travaille dessus
    if (prospect.commerciaux_actifs && prospect.commerciaux_actifs.length > 0) {
        const autres = prospect.commerciaux_actifs.filter(c => c.commercial !== currentUser);
        if (autres.length > 0) {
            badges += `<span style="background:#ff5722;color:white;padding:3px 8px;border-radius:12px;font-size:10px;margin-left:5px;" title="${autres.map(a => a.commercial).join(', ')} travaille dessus">🔴 EN COURS</span>`;
        }
    }
    
    return badges;
}
