let matchs = [];

// Couleurs pour les équipes
const teamColors = {
    'Manchester Red': '#e31e24',
    'Manchester Blue': '#6caddf',
    'London Blues': '#034694',
    'London Reds': '#d00000',
    'Liverpool': '#c8102e',
    'Newcastle': '#241f20',
    'Spurs': '#132257',
    'A. Villa': '#95bfe5',
    'Chelsea': '#034694',
    'Arsenal': '#ef0107',
    'Brighton': '#0057b8',
    'C. Palace': '#1b458f',
    'West Ham': '#7a2d6a',
    'Leeds': '#ffcd00',
    'Everton': '#003399',
    'Fulham': '#000000',
    'Bournemouth': '#da291c',
    'Sunderland': '#eb3b3b',
    'Burnley': '#6c1d45',
    'N. Forest': '#e5322e',
    'Wolverhampton': '#fdb913',
    'Brentford': '#e30613'
};

// Icônes pour les équipes
const teamIcons = {
    'Manchester Red': 'fa-bolt',
    'Manchester Blue': 'fa-water',
    'London Blues': 'fa-crown',
    'London Reds': 'fa-fire',
    'Liverpool': 'fa-anchor',
    'Newcastle': 'fa-building',
    'Spurs': 'fa-feather-alt',
    'A. Villa': 'fa-star',
    'Brighton': 'fa-sun',
    'C. Palace': 'fa-building',
    'West Ham': 'fa-hammer',
    'Leeds': 'fa-pepper-hot',
    'Everton': 'fa-apple-alt',
    'Fulham': 'fa-futbol',
    'Bournemouth': 'fa-umbrella-beach',
    'Sunderland': 'fa-ship',
    'Burnley': 'fa-mountain',
    'N. Forest': 'fa-tree',
    'Wolverhampton': 'fa-wolf-pack-battalion'
};

// Fonction pour vérifier si une équipe est déjà dans un match
function isTeamAlreadyScheduled(team) {
    return matchs.some(match => match.equipe1 === team || match.equipe2 === team);
}

function getTeamBadge(teamName) {
    const color = teamColors[teamName] || '#667eea';
    const icon = teamIcons[teamName] || 'fa-shield-alt';
    
    return `
        <div class="team-badge" style="background: ${color}">
            <div class="team-icon">
                <i class="fas ${icon}"></i>
            </div>
            ${teamName}
        </div>
    `;
}

function getTeamLogo(teamName, size = 'small') {
    const color = teamColors[teamName] || '#667eea';
    const icon = teamIcons[teamName] || 'fa-shield-alt';
    
    if (size === 'large') {
        return `
            <div style="display: inline-flex; align-items: center; gap: 8px;">
                <div style="width: 45px; height: 45px; background: ${color}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 1.2rem;">
                    <i class="fas ${icon}"></i>
                </div>
                <span style="font-weight: 700;">${teamName}</span>
            </div>
        `;
    } else {
        return `
            <div style="display: inline-flex; align-items: center; gap: 5px;">
                <div style="width: 30px; height: 30px; background: ${color}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 0.8rem;">
                    <i class="fas ${icon}"></i>
                </div>
                <span>${teamName}</span>
            </div>
        `;
    }
}

// Fonction pour désactiver les options sélectionnées
function updateEquipe2Options() {
    const equipe1 = document.getElementById("equipe1").value;
    const equipe2Select = document.getElementById("equipe2");
    const options = equipe2Select.options;
    
    for (let i = 0; i < options.length; i++) {
        const optionValue = options[i].value;
        // Désactiver si l'équipe est déjà sélectionnée dans equipe1 ou déjà dans un match
        if ((optionValue === equipe1 && equipe1 !== "") || isTeamAlreadyScheduled(optionValue)) {
            options[i].disabled = true;
            options[i].style.display = "none";
        } else if (optionValue !== "") {
            options[i].disabled = false;
            options[i].style.display = "";
        }
    }
    
    if (equipe2Select.value === equipe1 || isTeamAlreadyScheduled(equipe2Select.value)) {
        equipe2Select.value = "";
    }
}

function updateEquipe1Options() {
    const equipe2 = document.getElementById("equipe2").value;
    const equipe1Select = document.getElementById("equipe1");
    const options = equipe1Select.options;
    
    for (let i = 0; i < options.length; i++) {
        const optionValue = options[i].value;
        // Désactiver si l'équipe est déjà sélectionnée dans equipe2 ou déjà dans un match
        if ((optionValue === equipe2 && equipe2 !== "") || isTeamAlreadyScheduled(optionValue)) {
            options[i].disabled = true;
            options[i].style.display = "none";
        } else if (optionValue !== "") {
            options[i].disabled = false;
            options[i].style.display = "";
        }
    }
    
    if (equipe1Select.value === equipe2 || isTeamAlreadyScheduled(equipe1Select.value)) {
        equipe1Select.value = "";
    }
}

// Mettre à jour les options après chaque ajout ou suppression
function updateAllSelects() {
    updateEquipe1Options();
    updateEquipe2Options();
}

function resetSelects() {
    const equipe1Select = document.getElementById("equipe1");
    const equipe2Select = document.getElementById("equipe2");
    
    for (let i = 0; i < equipe1Select.options.length; i++) {
        const optionValue = equipe1Select.options[i].value;
        if (!isTeamAlreadyScheduled(optionValue) && optionValue !== "") {
            equipe1Select.options[i].disabled = false;
            equipe1Select.options[i].style.display = "";
        } else if (optionValue !== "") {
            equipe1Select.options[i].disabled = true;
            equipe1Select.options[i].style.display = "none";
        }
    }
    
    for (let i = 0; i < equipe2Select.options.length; i++) {
        const optionValue = equipe2Select.options[i].value;
        if (!isTeamAlreadyScheduled(optionValue) && optionValue !== "") {
            equipe2Select.options[i].disabled = false;
            equipe2Select.options[i].style.display = "";
        } else if (optionValue !== "") {
            equipe2Select.options[i].disabled = true;
            equipe2Select.options[i].style.display = "none";
        }
    }
    
    if (isTeamAlreadyScheduled(equipe1Select.value)) {
        equipe1Select.value = "";
    }
    if (isTeamAlreadyScheduled(equipe2Select.value)) {
        equipe2Select.value = "";
    }
}

function ajouterMatch() {
    const heure = document.getElementById("heure").value;
    const equipe1 = document.getElementById("equipe1").value;
    const equipe2 = document.getElementById("equipe2").value;

    if (heure === "" || equipe1 === "" || equipe2 === "") {
        alert("Veuillez remplir tous les champs.");
        return;
    }

    if (equipe1 === equipe2) {
        alert("Les équipes doivent être différentes.");
        return;
    }

    // Vérifier si une équipe est déjà programmée
    if (isTeamAlreadyScheduled(equipe1)) {
        alert(`L'équipe ${equipe1} est déjà programmée dans un match à ${matchs.find(m => m.equipe1 === equipe1 || m.equipe2 === equipe1).heure}.`);
        return;
    }
    
    if (isTeamAlreadyScheduled(equipe2)) {
        alert(`L'équipe ${equipe2} est déjà programmée dans un match à ${matchs.find(m => m.equipe1 === equipe2 || m.equipe2 === equipe2).heure}.`);
        return;
    }

    matchs.push({
        heure: heure,
        equipe1: equipe1,
        equipe2: equipe2
    });

    afficherMatchs();
    
    // Réinitialiser uniquement les sélections des équipes
    resetSelects();
}

function afficherMatchs() {
    const tbody = document.getElementById("matchsBody");
    const matchCount = document.getElementById("matchCount");
    
    matchCount.textContent = matchs.length;

    if (matchs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-muted py-4">
                    <i class="fas fa-info-circle"></i> Aucun match sélectionné
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = "";

    matchs.forEach((match, index) => {
        tbody.innerHTML += `
            <tr>
                <td class="text-center">
                    <span class="match-time">${match.heure}</span>
                </td>
                <td>${getTeamLogo(match.equipe1)}</td>
                <td class="text-center">
                    <span class="vs-badge">VS</span>
                </td>
                <td>${getTeamLogo(match.equipe2)}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-danger" onclick="supprimerMatch(${index})">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </td>
            </tr>
        `;
    });
}

function supprimerMatch(index) {
    matchs.splice(index, 1);
    afficherMatchs();
    document.getElementById("resultCard").style.display = "none";
    resetSelects();
    updateAllSelects();
}

function viderMatchs() {
    if (matchs.length > 0 && confirm("Voulez-vous vraiment vider la liste des matchs?")) {
        matchs = [];
        afficherMatchs();
        document.getElementById("resultCard").style.display = "none";
        resetSelects();
        updateAllSelects();
    }
}

function analyser() {
    if(matchs.length === 0){
        alert("Ajoutez au moins un match.");
        return;
    }

    const resultCard = document.getElementById("resultCard");
    const resultatDiv = document.getElementById("resultat");
    
    resultCard.style.display = "block";
    resultatDiv.innerHTML = `
        <div class="loading-spinner">
            <i class="fas fa-spinner"></i>
            <p class="mt-3">Analyse en cours...</p>
        </div>
    `;

    fetch('/analyser', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ matchs: matchs })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            resultatDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i> Erreur: ${data.error}
                </div>
            `;
            return;
        }
        
        afficherResultats(data.predictions);
        
        // APRÈS L'ANALYSE, on réinitialise l'heure à la valeur par défaut
        document.getElementById("heure").value = "17:15";
        
        // On réinitialise aussi les sélections des équipes
        resetSelects();
    })
    .catch(error => {
        resultatDiv.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i> Erreur lors de l'analyse: ${error.message}
            </div>
        `;
    });
}

function afficherResultats(predictions) {
    const resultatDiv = document.getElementById("resultat");
    
    let html = '';
    
    predictions.forEach((pred, idx) => {
        const predData = pred.prediction;
        
        let confidenceClass = 'confidence-low';
        if (predData.confidence === 'Élevé') confidenceClass = 'confidence-high';
        else if (predData.confidence === 'Moyen') confidenceClass = 'confidence-medium';
        
        html += `
            <div class="prediction-card">
                <div class="match-header">
                    <span class="match-time">
                        <i class="far fa-clock"></i> ${pred.heure}
                    </span>
                    <span class="${confidenceClass}">
                        <i class="fas fa-chart-line"></i> Confiance: ${predData.confidence}
                    </span>
                </div>
                
                <div class="text-center mb-4">
                    <div style="display: flex; justify-content: center; align-items: center; gap: 20px;">
                        ${getTeamLogo(pred.equipe1, 'large')}
                        <span style="font-size: 1.5rem; font-weight: 800; color: #667eea;">VS</span>
                        ${getTeamLogo(pred.equipe2, 'large')}
                    </div>
                </div>
                
                <div class="result-box text-center">
                    <div class="prediction-text">
                        <i class="fas fa-trophy"></i> PRONOSTIC : ${predData.prediction}
                    </div>
                    <div class="score-text">
                        Score probable : ${predData.expected_score}
                    </div>
                </div>
                
                <div class="mt-3">
                    <h6 class="text-center"><i class="fas fa-percent"></i> Probabilités</h6>
                    <div class="probability-bar">
                        <div class="prob-win" style="width: ${predData.team1_win_prob}%;">
                            ${pred.equipe1}: ${predData.team1_win_prob}%
                        </div>
                        <div class="prob-draw" style="width: ${predData.draw_prob}%;">
                            Nul: ${predData.draw_prob}%
                        </div>
                        <div class="prob-loss" style="width: ${predData.team2_win_prob}%;">
                            ${pred.equipe2}: ${predData.team2_win_prob}%
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    resultatDiv.innerHTML = html;
    document.getElementById("resultCard").scrollIntoView({ behavior: 'smooth' });
}

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', function() {
    resetSelects();
});