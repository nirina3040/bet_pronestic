from flask import Flask, render_template, request, jsonify
import pandas as pd
from collections import defaultdict
import os
import numpy as np
import pickle
from waitress import serve
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, log_loss, classification_report
from scipy.stats import poisson

app = Flask(__name__)

DATA_PATH = 'data/virtual_stats.xlsx'
MODEL_PATH = 'model.pkl'
SHEET_NAME = 'Sheet1'

EQUIPES = [
    "Manchester Red", "Manchester Blue", "London Blues", "London Reds",
    "Liverpool", "Newcastle", "Brentford", "Wolverhampton", "Spurs",
    "A. Villa", "Brighton", "C. Palace", "West Ham", "Leeds", "Everton",
    "Fulham", "Bournemouth", "Sunderland", "Burnley", "N. Forest"
]

calibrated_model = None


def safe_int_score(score):
    if pd.isna(score):
        return None
    s = str(score).strip()
    if ':' not in s:
        return None
    try:
        a, b = s.split(':')
        return int(a), int(b)
    except:
        return None


def load_match_data():
    try:
        df = pd.read_excel(DATA_PATH, sheet_name=SHEET_NAME)
        if not isinstance(df, pd.DataFrame) or df.empty:
            return {}, [], 1.25, pd.DataFrame()

        required_cols = {'equipe 1', 'equipe 2', 'score final'}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(f"Colonnes requises manquantes: {required_cols - set(df.columns)}")

        team_stats = defaultdict(lambda: {
            'played': 0, 'wins': 0, 'draws': 0, 'losses': 0,
            'goals_for': 0, 'goals_against': 0,
            'home_played': 0, 'away_played': 0,
            'home_goals_for': 0, 'home_goals_against': 0,
            'away_goals_for': 0, 'away_goals_against': 0
        })

        matches_history = []
        total_goals = 0
        total_matches = 0

        for _, row in df.iterrows():
            equipe1 = str(row['equipe 1']).strip()
            equipe2 = str(row['equipe 2']).strip()
            parsed = safe_int_score(row['score final'])
            if not parsed:
                continue

            goals1, goals2 = parsed
            total_matches += 1
            total_goals += goals1 + goals2

            team_stats[equipe1]['played'] += 1
            team_stats[equipe2]['played'] += 1

            team_stats[equipe1]['goals_for'] += goals1
            team_stats[equipe1]['goals_against'] += goals2
            team_stats[equipe2]['goals_for'] += goals2
            team_stats[equipe2]['goals_against'] += goals1

            team_stats[equipe1]['home_played'] += 1
            team_stats[equipe2]['away_played'] += 1

            team_stats[equipe1]['home_goals_for'] += goals1
            team_stats[equipe1]['home_goals_against'] += goals2
            team_stats[equipe2]['away_goals_for'] += goals2
            team_stats[equipe2]['away_goals_against'] += goals1

            if goals1 > goals2:
                team_stats[equipe1]['wins'] += 1
                team_stats[equipe2]['losses'] += 1
            elif goals1 < goals2:
                team_stats[equipe2]['wins'] += 1
                team_stats[equipe1]['losses'] += 1
            else:
                team_stats[equipe1]['draws'] += 1
                team_stats[equipe2]['draws'] += 1

            matches_history.append({
                'equipe1': equipe1,
                'equipe2': equipe2,
                'goals1': goals1,
                'goals2': goals2
            })

        league_avg_goals_per_team = (total_goals / total_matches / 2) if total_matches > 0 else 1.25
        return team_stats, matches_history, league_avg_goals_per_team, df

    except Exception as e:
        print(f"Erreur lors du chargement des données: {e}")
        return {}, [], 1.25, pd.DataFrame()


def calculate_head_to_head(team1, team2, matches_history):
    team1_wins = team2_wins = draws = 0
    total_goals1 = total_goals2 = 0
    matches_played = 0

    for match in matches_history:
        if (match['equipe1'] == team1 and match['equipe2'] == team2) or \
           (match['equipe1'] == team2 and match['equipe2'] == team1):
            matches_played += 1
            if match['equipe1'] == team1:
                goals1, goals2 = match['goals1'], match['goals2']
            else:
                goals1, goals2 = match['goals2'], match['goals1']

            total_goals1 += goals1
            total_goals2 += goals2

            if goals1 > goals2:
                team1_wins += 1
            elif goals1 < goals2:
                team2_wins += 1
            else:
                draws += 1

    return {
        'matches_played': matches_played,
        'team1_wins': team1_wins,
        'team2_wins': team2_wins,
        'draws': draws,
        'total_goals1': total_goals1,
        'total_goals2': total_goals2,
        'win_rate1': (team1_wins / matches_played * 100) if matches_played > 0 else 33.3,
        'win_rate2': (team2_wins / matches_played * 100) if matches_played > 0 else 33.3,
        'draw_rate': (draws / matches_played * 100) if matches_played > 0 else 33.3
    }


def expected_goals(team, opponent, team_stats, league_avg, is_home=True):
    t = team_stats.get(team, {})
    o = team_stats.get(opponent, {})

    if is_home:
        team_played = max(t.get('home_played', 0), 1)
        opp_played = max(o.get('away_played', 0), 1)
        team_attack = (t.get('home_goals_for', 0) / team_played) / max(league_avg, 0.01)
        opp_defense = (o.get('away_goals_against', 0) / opp_played) / max(league_avg, 0.01)
    else:
        team_played = max(t.get('away_played', 0), 1)
        opp_played = max(o.get('home_played', 0), 1)
        team_attack = (t.get('away_goals_for', 0) / team_played) / max(league_avg, 0.01)
        opp_defense = (o.get('home_goals_against', 0) / opp_played) / max(league_avg, 0.01)

    lam = league_avg * team_attack * opp_defense
    return max(0.15, min(lam, 5.0))


def recent_form(team, matches_history, last_n=5):
    relevant = []
    for m in reversed(matches_history):
        if m['equipe1'] == team or m['equipe2'] == team:
            if m['equipe1'] == team:
                gf, ga = m['goals1'], m['goals2']
            else:
                gf, ga = m['goals2'], m['goals1']
            if gf > ga:
                res = 1
            elif gf < ga:
                res = 0
            else:
                res = 0.5
            relevant.append((res, gf, ga))
        if len(relevant) >= last_n:
            break

    if not relevant:
        return {'points_rate': 0.5, 'gf_avg': 0.0, 'ga_avg': 0.0}

    points_rate = sum(x[0] for x in relevant) / len(relevant)
    gf_avg = sum(x[1] for x in relevant) / len(relevant)
    ga_avg = sum(x[2] for x in relevant) / len(relevant)
    return {'points_rate': points_rate, 'gf_avg': gf_avg, 'ga_avg': ga_avg}


def build_dataset(team_stats, matches_history, league_avg, df):
    X, y = [], []

    for _, row in df.iterrows():
        equipe1 = str(row['equipe 1']).strip()
        equipe2 = str(row['equipe 2']).strip()
        parsed = safe_int_score(row['score final'])
        if not parsed:
            continue

        goals1, goals2 = parsed

        lam1 = expected_goals(equipe1, equipe2, team_stats, league_avg, True)
        lam2 = expected_goals(equipe2, equipe1, team_stats, league_avg, False)
        h2h = calculate_head_to_head(equipe1, equipe2, matches_history)

        f1 = team_stats.get(equipe1, {})
        f2 = team_stats.get(equipe2, {})
        form1 = recent_form(equipe1, matches_history, 5)
        form2 = recent_form(equipe2, matches_history, 5)

        features = [
            lam1, lam2,
            h2h['matches_played'],
            h2h['win_rate1'], h2h['win_rate2'], h2h['draw_rate'],
            f1.get('wins', 0) / max(f1.get('played', 1), 1),
            f2.get('wins', 0) / max(f2.get('played', 1), 1),
            f1.get('goals_for', 0) / max(f1.get('played', 1), 1),
            f2.get('goals_for', 0) / max(f2.get('played', 1), 1),
            f1.get('goals_against', 0) / max(f1.get('played', 1), 1),
            f2.get('goals_against', 0) / max(f2.get('played', 1), 1),
            form1['points_rate'], form2['points_rate'],
            form1['gf_avg'], form2['gf_avg'],
            form1['ga_avg'], form2['ga_avg'],
        ]

        X.append(features)

        if goals1 > goals2:
            y.append(0)
        elif goals1 < goals2:
            y.append(1)
        else:
            y.append(2)

    return np.array(X), np.array(y)


def train_calibrated_model(X, y):
    unique_classes = np.unique(y)
    stratify_value = y if len(unique_classes) > 1 else None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify_value
    )

    base_model = RandomForestClassifier(
        n_estimators=800,
        max_depth=12,
        min_samples_leaf=3,
        min_samples_split=6,
        random_state=42,
        class_weight='balanced_subsample'
    )
    base_model.fit(X_train, y_train)

    try:
        calibrated = CalibratedClassifierCV(estimator=base_model, cv='prefit', method='sigmoid')
        calibrated.fit(X_test, y_test)
    except TypeError:
        calibrated = CalibratedClassifierCV(base_model, method='sigmoid', cv=3)
        calibrated.fit(X, y)

    pred = base_model.predict(X_test)
    prob = calibrated.predict_proba(X_test)

    metrics = {
        'accuracy': float(accuracy_score(y_test, pred)),
        'log_loss': float(log_loss(y_test, prob, labels=[0, 1, 2])),
        'report': classification_report(y_test, pred, output_dict=True, zero_division=0)
    }

    return calibrated, metrics


def load_calibrated_model():
    global calibrated_model
    if calibrated_model is not None:
        return calibrated_model

    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, 'rb') as f:
                calibrated_model = pickle.load(f)
            print("Modèle chargé depuis le fichier.")
            return calibrated_model
        except Exception as e:
            print(f"Erreur chargement modèle: {e}")
    return None


def init_model():
    global calibrated_model
    team_stats, matches_history, league_avg, df = load_match_data()
    if not team_stats or len(df) == 0:
        calibrated_model = None
        print("Aucune donnée valide pour le modèle.")
        return

    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, 'rb') as f:
                calibrated_model = pickle.load(f)
            print("Modèle déjà présent, chargé automatiquement.")
            return
        except Exception as e:
            print(f"Erreur lecture modèle: {e}")

    X, y = build_dataset(team_stats, matches_history, league_avg, df)
    if len(X) < 20:
        calibrated_model = None
        print("Pas assez de données pour entraîner le modèle.")
        return

    calibrated_model, metrics = train_calibrated_model(X, y)

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(calibrated_model, f)

    print("Modèle entraîné et sauvegardé avec succès.")
    print(metrics)


def predict_poisson_correct_score(lam1, lam2, max_goals=6):
    home_probs = [poisson.pmf(i, lam1) for i in range(0, max_goals + 1)]
    away_probs = [poisson.pmf(j, lam2) for j in range(0, max_goals + 1)]

    score_matrix = np.outer(home_probs, away_probs)

    correct_score_probs = {}
    best_score = None
    best_prob = -1

    for i in range(0, max_goals + 1):
        for j in range(0, max_goals + 1):
            prob = score_matrix[i, j]
            key = f"{i}:{j}"
            correct_score_probs[key] = prob
            if prob > best_prob:
                best_prob = prob
                best_score = key

    total_prob = sum(correct_score_probs.values())
    return correct_score_probs, best_score, best_prob, total_prob


def predict_with_model_and_poisson(team1, team2, team_stats, matches_history, league_avg, model):
    stats1 = team_stats.get(team1, {'played': 0})
    stats2 = team_stats.get(team2, {'played': 0})

    if stats1.get('played', 0) == 0 or stats2.get('played', 0) == 0:
        return {
            'team1_win_prob': 33.33,
            'team2_win_prob': 33.33,
            'draw_prob': 33.34,
            'expected_score': "0:0",
            'most_likely_score': "0:0",
            'most_likely_score_prob': 0.0,
            'prediction': "Données insuffisantes",
            'confidence': "Faible",
            'use_calibration': False,
            'correct_scores': {}
        }

    h2h = calculate_head_to_head(team1, team2, matches_history)
    lam1 = expected_goals(team1, team2, team_stats, league_avg, True)
    lam2 = expected_goals(team2, team1, team_stats, league_avg, False)
    form1 = recent_form(team1, matches_history, 5)
    form2 = recent_form(team2, matches_history, 5)

    if h2h['matches_played'] > 0:
        lam1 = 0.85 * lam1 + 0.15 * (h2h['total_goals1'] / h2h['matches_played'])
        lam2 = 0.85 * lam2 + 0.15 * (h2h['total_goals2'] / h2h['matches_played'])

    features = np.array([[
        lam1, lam2,
        h2h['matches_played'],
        h2h['win_rate1'], h2h['win_rate2'], h2h['draw_rate'],
        stats1.get('wins', 0) / max(stats1.get('played', 1), 1),
        stats2.get('wins', 0) / max(stats2.get('played', 1), 1),
        stats1.get('goals_for', 0) / max(stats1.get('played', 1), 1),
        stats2.get('goals_for', 0) / max(stats2.get('played', 1), 1),
        stats1.get('goals_against', 0) / max(stats1.get('played', 1), 1),
        stats2.get('goals_against', 0) / max(stats2.get('played', 1), 1),
        form1['points_rate'], form2['points_rate'],
        form1['gf_avg'], form2['gf_avg'],
        form1['ga_avg'], form2['ga_avg'],
    ]])

    if model is not None:
        probs = model.predict_proba(features)[0] * 100
        home_win = round(float(probs[0]), 1)
        away_win = round(float(probs[1]), 1)
        draw = round(float(probs[2]), 1)
        use_calibration = True
    else:
        home_win, away_win, draw = 33.3, 33.3, 33.4
        use_calibration = False

    if home_win >= away_win and home_win >= draw:
        prediction = f"{team1} gagne"
    elif away_win >= home_win and away_win >= draw:
        prediction = f"{team2} gagne"
    else:
        prediction = "Match nul"

    if h2h['matches_played'] >= 5 and stats1.get('played', 0) >= 15 and stats2.get('played', 0) >= 15:
        confidence = "Élevé"
    elif h2h['matches_played'] >= 2 and stats1.get('played', 0) >= 8 and stats2.get('played', 0) >= 8:
        confidence = "Moyen"
    else:
        confidence = "Faible"

    correct_scores, best_score, best_prob, total_prob = predict_poisson_correct_score(lam1, lam2, max_goals=6)
    correct_scores_percent = {k: round(v * 100, 2) for k, v in correct_scores.items()}
    best_prob_percent = round(best_prob * 100, 2)

    return {
        'team1_win_prob': home_win,
        'team2_win_prob': away_win,
        'draw_prob': draw,
        'expected_score': f"{round(lam1)}:{round(lam2)}",
        'most_likely_score': best_score,
        'most_likely_score_prob': best_prob_percent,
        'correct_scores': correct_scores_percent,
        'prediction': prediction,
        'confidence': confidence,
        'team1_stats': {
            'played': stats1.get('played', 0),
            'wins': stats1.get('wins', 0),
            'draws': stats1.get('draws', 0),
            'losses': stats1.get('losses', 0),
            'avg_goals': round(stats1.get('goals_for', 0) / max(stats1.get('played', 1), 1), 2) if stats1.get('played', 0) > 0 else 0,
            'avg_conceded': round(stats1.get('goals_against', 0) / max(stats1.get('played', 1), 1), 2) if stats1.get('played', 0) > 0 else 0
        },
        'team2_stats': {
            'played': stats2.get('played', 0),
            'wins': stats2.get('wins', 0),
            'draws': stats2.get('draws', 0),
            'losses': stats2.get('losses', 0),
            'avg_goals': round(stats2.get('goals_for', 0) / max(stats2.get('played', 1), 1), 2) if stats2.get('played', 0) > 0 else 0,
            'avg_conceded': round(stats2.get('goals_against', 0) / max(stats2.get('played', 1), 1), 2) if stats2.get('played', 0) > 0 else 0
        },
        'head_to_head': h2h,
        'use_calibration': use_calibration
    }


@app.route("/")
def index():
    return render_template("index.html", equipes=EQUIPES)


@app.route("/train-model", methods=['POST'])
def train_model():
    try:
        team_stats, matches_history, league_avg, df = load_match_data()
        if not team_stats or len(df) == 0:
            return jsonify({'error': 'Erreur lors du chargement des données'}), 500

        X, y = build_dataset(team_stats, matches_history, league_avg, df)
        if len(X) < 20:
            return jsonify({'error': 'Pas assez de données pour entraîner le modèle'}), 400

        model, metrics = train_calibrated_model(X, y)

        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(model, f)

        global calibrated_model
        calibrated_model = model

        return jsonify({
            'message': 'Modèle entraîné et calibré avec succès',
            'n_samples': int(len(X)),
            'accuracy': metrics['accuracy'],
            'log_loss': metrics['log_loss']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/analyser", methods=['POST'])
def analyser():
    try:
        data = request.get_json(force=True)
        matchs = data.get('matchs', [])

        if not matchs:
            return jsonify({'error': 'Aucun match à analyser'}), 400

        team_stats, matches_history, league_avg, df = load_match_data()
        if not team_stats:
            return jsonify({'error': 'Erreur lors du chargement des données'}), 500

        model = load_calibrated_model()

        predictions = []
        for match in matchs:
            equipe1 = match.get('equipe1')
            equipe2 = match.get('equipe2')
            heure = match.get('heure', '')

            if not equipe1 or not equipe2:
                continue

            pred = predict_with_model_and_poisson(equipe1, equipe2, team_stats, matches_history, league_avg, model)
            predictions.append({
                'heure': heure,
                'equipe1': equipe1,
                'equipe2': equipe2,
                'prediction': pred
            })

        return jsonify({'predictions': predictions})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    init_model()
    serve(app, host="0.0.0.0", port=5000)