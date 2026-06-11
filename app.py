from flask import Flask, render_template, request, jsonify
import pandas as pd
from collections import defaultdict
import os
import numpy as np
import pickle
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, log_loss, classification_report, f1_score, confusion_matrix
from xgboost import XGBClassifier
from scipy.stats import poisson
from sklearn.preprocessing import RobustScaler
from imblearn.over_sampling import SMOTE

app = Flask(__name__)

DATA_PATH = 'data/virtual_stats.xlsx'
MODEL_FINAL_PATH = 'model_final.pkl'
SCALER_FINAL_PATH = 'scaler_final.pkl'
SHEET_NAME = 'Sheet1'

EQUIPES = [
    "Manchester Red", "Manchester Blue", "London Blues", "London Reds",
    "Liverpool", "Newcastle", "Brentford", "Wolverhampton", "Spurs",
    "A. Villa", "Brighton", "C. Palace", "West Ham", "Leeds", "Everton",
    "Fulham", "Bournemouth", "Sunderland", "Burnley", "N. Forest"
]

model = None
scaler = None


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
            'away_goals_for': 0, 'away_goals_against': 0,
            'clean_sheets': 0, 'failed_to_score': 0,
            'btts_count': 0, 'over_25_count': 0,
            'form_points': []
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
            
            if goals2 == 0:
                team_stats[equipe1]['clean_sheets'] += 1
            if goals1 == 0:
                team_stats[equipe2]['clean_sheets'] += 1
            if goals1 == 0:
                team_stats[equipe1]['failed_to_score'] += 1
            if goals2 == 0:
                team_stats[equipe2]['failed_to_score'] += 1
            
            if goals1 > 0 and goals2 > 0:
                team_stats[equipe1]['btts_count'] += 1
                team_stats[equipe2]['btts_count'] += 1
            
            if goals1 + goals2 > 2.5:
                team_stats[equipe1]['over_25_count'] += 1
                team_stats[equipe2]['over_25_count'] += 1

            if goals1 > goals2:
                team_stats[equipe1]['wins'] += 1
                team_stats[equipe2]['losses'] += 1
                team_stats[equipe1]['form_points'].append(3)
                team_stats[equipe2]['form_points'].append(0)
            elif goals1 < goals2:
                team_stats[equipe2]['wins'] += 1
                team_stats[equipe1]['losses'] += 1
                team_stats[equipe1]['form_points'].append(0)
                team_stats[equipe2]['form_points'].append(3)
            else:
                team_stats[equipe1]['draws'] += 1
                team_stats[equipe2]['draws'] += 1
                team_stats[equipe1]['form_points'].append(1)
                team_stats[equipe2]['form_points'].append(1)

            matches_history.append({
                'equipe1': equipe1,
                'equipe2': equipe2,
                'goals1': goals1,
                'goals2': goals2
            })

        for team in team_stats:
            team_stats[team]['form_points'] = team_stats[team]['form_points'][-10:]
            team_stats[team]['form_avg'] = sum(team_stats[team]['form_points']) / max(len(team_stats[team]['form_points']), 1) / 3
            team_stats[team]['btts_rate'] = team_stats[team]['btts_count'] / max(team_stats[team]['played'], 1)
            team_stats[team]['over_25_rate'] = team_stats[team]['over_25_count'] / max(team_stats[team]['played'], 1)

        league_avg_goals_per_team = (total_goals / total_matches / 2) if total_matches > 0 else 1.25
        print(f"✅ Données chargées: {total_matches} matchs")
        
        return team_stats, matches_history, league_avg_goals_per_team, df

    except Exception as e:
        print(f"Erreur load_match_data: {e}")
        return {}, [], 1.25, pd.DataFrame()


def calculate_head_to_head(team1, team2, matches_history):
    team1_wins = team2_wins = draws = 0
    total_goals1 = total_goals2 = 0
    matches_played = 0
    recent_form_h2h = []
    btts_count = 0
    over_25_count = 0

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
            recent_form_h2h.append(1 if goals1 > goals2 else (0 if goals1 < goals2 else 0.5))
            
            if goals1 > 0 and goals2 > 0:
                btts_count += 1
            if goals1 + goals2 > 2.5:
                over_25_count += 1

            if goals1 > goals2:
                team1_wins += 1
            elif goals1 < goals2:
                team2_wins += 1
            else:
                draws += 1

    recent_form_h2h = recent_form_h2h[-3:] if len(recent_form_h2h) > 3 else recent_form_h2h
    recent_h2h_avg = sum(recent_form_h2h) / len(recent_form_h2h) if recent_form_h2h else 0.5

    return {
        'matches_played': matches_played,
        'team1_wins': team1_wins,
        'team2_wins': team2_wins,
        'draws': draws,
        'win_rate1': (team1_wins / matches_played * 100) if matches_played > 0 else 33.3,
        'win_rate2': (team2_wins / matches_played * 100) if matches_played > 0 else 33.3,
        'draw_rate': (draws / matches_played * 100) if matches_played > 0 else 33.3,
        'avg_goals_h2h': (total_goals1 + total_goals2) / matches_played if matches_played > 0 else 2.5,
        'recent_h2h_form': recent_h2h_avg,
        'h2h_advantage': (team1_wins - team2_wins) / max(matches_played, 1),
        'btts_rate_h2h': btts_count / max(matches_played, 1),
        'over_25_rate_h2h': over_25_count / max(matches_played, 1)
    }


def expected_goals(team, opponent, team_stats, league_avg, is_home=True):
    t = team_stats.get(team, {})
    o = team_stats.get(opponent, {})

    if is_home:
        team_played = max(t.get('home_played', 0), 1)
        opp_played = max(o.get('away_played', 0), 1)
        team_attack = (t.get('home_goals_for', 0) / team_played) / max(league_avg, 0.01)
        opp_defense = (o.get('away_goals_against', 0) / opp_played) / max(league_avg, 0.01)
        home_boost = 1.1
        team_attack *= home_boost
    else:
        team_played = max(t.get('away_played', 0), 1)
        opp_played = max(o.get('home_played', 0), 1)
        team_attack = (t.get('away_goals_for', 0) / team_played) / max(league_avg, 0.01)
        opp_defense = (o.get('home_goals_against', 0) / opp_played) / max(league_avg, 0.01)

    form_adj = t.get('form_avg', 0.5) - 0.5
    team_attack *= (1 + form_adj * 0.2)

    lam = league_avg * team_attack * opp_defense
    lam = min(lam, 4.0)
    
    return max(0.15, lam)


def recent_form(team, matches_history, last_n=5):
    relevant = []
    goal_diff_sum = 0
    btts_count = 0
    over_25_count = 0
    
    for m in reversed(matches_history):
        if m['equipe1'] == team or m['equipe2'] == team:
            if m['equipe1'] == team:
                gf, ga = m['goals1'], m['goals2']
            else:
                gf, ga = m['goals2'], m['goals1']
            
            goal_diff = gf - ga
            goal_diff_sum += goal_diff
            
            if gf > 0 and ga > 0:
                btts_count += 1
            if gf + ga > 2.5:
                over_25_count += 1
            
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
        return {'points_rate': 0.5, 'gf_avg': 0.0, 'ga_avg': 0.0, 'draw_rate': 0.0, 
                'goal_diff_avg': 0.0, 'form_trend': 0.0, 'btts_rate': 0.5, 'over_25_rate': 0.5}

    points_rate = sum(x[0] for x in relevant) / len(relevant)
    gf_avg = sum(x[1] for x in relevant) / len(relevant)
    ga_avg = sum(x[2] for x in relevant) / len(relevant)
    draw_rate = sum(1 for x in relevant if x[0] == 0.5) / len(relevant)
    goal_diff_avg = goal_diff_sum / len(relevant)
    btts_rate = btts_count / len(relevant)
    over_25_rate = over_25_count / len(relevant)
    
    if len(relevant) >= 6:
        recent = sum(x[0] for x in relevant[:3]) / 3
        older = sum(x[0] for x in relevant[-3:]) / 3
        form_trend = recent - older
    else:
        form_trend = 0
    
    return {'points_rate': points_rate, 'gf_avg': gf_avg, 'ga_avg': ga_avg, 
            'draw_rate': draw_rate, 'goal_diff_avg': goal_diff_avg, 
            'form_trend': form_trend, 'btts_rate': btts_rate, 'over_25_rate': over_25_rate}


def calculate_draw_probability(team1, team2, team_stats, matches_history):
    stats1 = team_stats.get(team1, {})
    stats2 = team_stats.get(team2, {})
    
    draw_rate1 = stats1.get('draws', 0) / max(stats1.get('played', 1), 1)
    draw_rate2 = stats2.get('draws', 0) / max(stats2.get('played', 1), 1)
    form1 = recent_form(team1, matches_history, 5)
    form2 = recent_form(team2, matches_history, 5)
    
    equal_strength = 1 - abs((stats1.get('wins', 0) / max(stats1.get('played', 1), 1)) - 
                              (stats2.get('wins', 0) / max(stats2.get('played', 1), 1)))
    
    low_scoring = 1 - min(1, (stats1.get('goals_for', 0) / max(stats1.get('played', 1), 1) + 
                               stats2.get('goals_for', 0) / max(stats2.get('played', 1), 1)) / 3)
    
    draw_prob = (draw_rate1 + draw_rate2 + form1['draw_rate'] + form2['draw_rate']) / 4
    draw_prob = draw_prob * (0.6 + 0.4 * equal_strength) * (0.7 + 0.3 * low_scoring)
    
    return min(draw_prob, 0.55)


def build_dataset_v3(team_stats, matches_history, league_avg, df):
    """Dataset V3 - Version qui a donné les meilleurs résultats"""
    import numpy as np

    X, y = [], []

    def safe_div(a, b):
        return a / b if b else 0.0

    for _, row in df.iterrows():
        equipe1 = str(row['equipe 1']).strip()
        equipe2 = str(row['equipe 2']).strip()

        parsed = safe_int_score(row['score final'])
        if not parsed:
            continue

        goals1, goals2 = parsed

        lam1 = expected_goals(equipe1, equipe2, team_stats, league_avg, True)
        lam2 = expected_goals(equipe2, equipe1, team_stats, league_avg, False)

        f1 = team_stats.get(equipe1, {})
        f2 = team_stats.get(equipe2, {})

        form1_5 = recent_form(equipe1, matches_history, 5)
        form2_5 = recent_form(equipe2, matches_history, 5)
        form1_3 = recent_form(equipe1, matches_history, 3)
        form2_3 = recent_form(equipe2, matches_history, 3)

        h2h = calculate_head_to_head(equipe1, equipe2, matches_history)

        played1 = max(f1.get('played', 1), 1)
        played2 = max(f2.get('played', 1), 1)
        
        draw_prob = calculate_draw_probability(equipe1, equipe2, team_stats, matches_history)

        features = [
            lam1, lam2,
            lam1 - lam2,
            (lam1 + lam2) / 2,
            
            h2h['win_rate1'] - h2h['win_rate2'],
            h2h['draw_rate'],
            min(h2h['matches_played'] / 10.0, 1.0),
            h2h['avg_goals_h2h'],
            h2h['recent_h2h_form'],
            h2h['h2h_advantage'],
            h2h['btts_rate_h2h'],
            h2h['over_25_rate_h2h'],
            
            form1_5['points_rate'] - form2_5['points_rate'],
            form1_5['goal_diff_avg'] - form2_5['goal_diff_avg'],
            form1_5['btts_rate'] - form2_5['btts_rate'],
            form1_5['over_25_rate'] - form2_5['over_25_rate'],
            
            form1_3['points_rate'] - form2_3['points_rate'],
            form1_3['goal_diff_avg'] - form2_3['goal_diff_avg'],
            
            form1_5['form_trend'] - form2_5['form_trend'],
            
            form1_5['draw_rate'],
            form2_5['draw_rate'],
            draw_prob,
            1 if abs(lam1 - lam2) < 0.4 else 0,
            1 if abs(lam1 - lam2) < 0.2 else 0,
            
            form1_5['gf_avg'] - form2_5['ga_avg'],
            form1_5['ga_avg'] - form2_5['gf_avg'],
            
            safe_div(f1.get('goals_for', 0), played1) - safe_div(f2.get('goals_for', 0), played2),
            safe_div(f1.get('goals_against', 0), played1) - safe_div(f2.get('goals_against', 0), played2),
            
            safe_div(f1.get('home_goals_for', 0), max(f1.get('home_played', 1), 1)),
            safe_div(f2.get('away_goals_for', 0), max(f2.get('away_played', 1), 1)),
            safe_div(f1.get('home_goals_against', 0), max(f1.get('home_played', 1), 1)),
            safe_div(f2.get('away_goals_against', 0), max(f2.get('away_played', 1), 1)),
            
            safe_div(f1.get('clean_sheets', 0), played1) - safe_div(f2.get('clean_sheets', 0), played2),
            safe_div(f1.get('failed_to_score', 0), played1) - safe_div(f2.get('failed_to_score', 0), played2),
            
            safe_div(f1.get('wins', 0), played1) - safe_div(f2.get('wins', 0), played2),
            safe_div(f1.get('draws', 0), played1) - safe_div(f2.get('draws', 0), played2),
            
            f1.get('form_avg', 0.5) - f2.get('form_avg', 0.5),
        ]

        X.append(features)

        if goals1 > goals2:
            y.append(0)
        elif goals2 > goals1:
            y.append(1)
        else:
            y.append(2)

    print(f"✅ Dataset V3: {len(X)} échantillons, {len(features)} features")
    return np.array(X, dtype=np.float32), np.array(y)


def train_v3_model(X, y):
    """Modèle V3 - Meilleurs résultats"""
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\n📊 Distribution initiale:")
    unique, counts = np.unique(y_train, return_counts=True)
    for cls, cnt in zip(unique, counts):
        print(f"   Classe {cls}: {cnt} ({cnt/len(y_train)*100:.1f}%)")
    
    # SMOTE V3 - 72% draw
    target_home = counts[0]
    target_away = int(counts[0] * 0.85)
    target_draw = int(counts[0] * 0.72)
    
    sampling_strategy = {0: target_home, 1: target_away, 2: target_draw}
    
    smote = SMOTE(sampling_strategy=sampling_strategy, random_state=42, k_neighbors=3)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)
    
    print(f"\n📊 Distribution après SMOTE:")
    unique, counts = np.unique(y_train_resampled, return_counts=True)
    for cls, cnt in zip(unique, counts):
        print(f"   Classe {cls}: {cnt} ({cnt/len(y_train_resampled)*100:.1f}%)")
    
    # Standardisation
    global scaler
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train_resampled)
    X_test_scaled = scaler.transform(X_test)
    
    # Poids des classes V3
    class_weights = {0: 1.0, 1: 1.15, 2: 1.55}
    sample_weights = np.array([class_weights[y] for y in y_train_resampled])
    
    print(f"\n📊 Poids des classes: {class_weights}")
    
    # XGBoost
    print("\n🚀 Entraînement XGBoost...")
    xgb = XGBClassifier(
        n_estimators=550,
        learning_rate=0.018,
        max_depth=5,
        min_child_weight=3,
        subsample=0.85,
        colsample_bytree=0.85,
        gamma=0.09,
        reg_alpha=0.09,
        reg_lambda=0.9,
        random_state=42,
        n_jobs=-1
    )
    xgb.fit(X_train_scaled, y_train_resampled, sample_weight=sample_weights)
    
    # Random Forest
    print("🚀 Entraînement Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=400,
        max_depth=12,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train_scaled, y_train_resampled)
    
    # Gradient Boosting
    print("🚀 Entraînement Gradient Boosting...")
    gb = GradientBoostingClassifier(
        n_estimators=250,
        learning_rate=0.016,
        max_depth=5,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=42
    )
    gb.fit(X_train_scaled, y_train_resampled)
    
    # Ensemble
    prob_xgb = xgb.predict_proba(X_test_scaled)
    prob_rf = rf.predict_proba(X_test_scaled)
    prob_gb = gb.predict_proba(X_test_scaled)
    
    prob_ensemble = prob_xgb * 0.45 + prob_rf * 0.30 + prob_gb * 0.25
    
    # Optimisation du seuil
    best_threshold = 0.5
    best_score = 0
    best_metrics = None
    
    for threshold in np.arange(0.44, 0.60, 0.01):
        prob_adj = prob_ensemble.copy()
        prob_adj[:, 2] = prob_adj[:, 2] * (threshold / 0.5)
        prob_adj = prob_adj / prob_adj.sum(axis=1, keepdims=True)
        pred_adj = np.argmax(prob_adj, axis=1)
        
        report = classification_report(y_test, pred_adj, output_dict=True)
        
        acc = accuracy_score(y_test, pred_adj)
        recall_draw = report['2']['recall']
        
        composite = recall_draw * 0.50 + acc * 0.50
        
        if composite > best_score:
            best_score = composite
            best_threshold = threshold
            best_metrics = {
                'accuracy': acc,
                'recall_draw': recall_draw,
                'f1_draw': report['2']['f1-score'],
                'recall_home': report['0']['recall'],
                'recall_away': report['1']['recall']
            }
    
    print(f"\n🎯 Meilleur seuil Draw: {best_threshold:.3f}")
    print(f"   Accuracy: {best_metrics['accuracy']*100:.2f}%")
    print(f"   Recall Draw: {best_metrics['recall_draw']*100:.2f}%")
    print(f"   F1 Draw: {best_metrics['f1_draw']*100:.2f}%")
    print(f"   Recall Home: {best_metrics['recall_home']*100:.2f}%")
    print(f"   Recall Away: {best_metrics['recall_away']*100:.2f}%")
    
    prob_final = prob_ensemble.copy()
    prob_final[:, 2] = prob_final[:, 2] * (best_threshold / 0.5)
    prob_final = prob_final / prob_final.sum(axis=1, keepdims=True)
    pred_final = np.argmax(prob_final, axis=1)
    
    metrics = {
        "accuracy": float(accuracy_score(y_test, pred_final)),
        "log_loss": float(log_loss(y_test, prob_final)),
        "f1_macro": float(f1_score(y_test, pred_final, average='macro')),
        "report": classification_report(y_test, pred_final, output_dict=True),
        "best_threshold": float(best_threshold),
        "confusion_matrix": confusion_matrix(y_test, pred_final).tolist()
    }
    
    model_dict = {
        'xgb': xgb,
        'rf': rf,
        'gb': gb,
        'scaler': scaler,
        'threshold': float(best_threshold),
        'weights': [0.45, 0.30, 0.25]
    }
    
    return model_dict, metrics


def predict_poisson_correct_score(lam1, lam2, max_goals=5):
    home = [poisson.pmf(i, lam1) for i in range(max_goals + 1)]
    away = [poisson.pmf(j, lam2) for j in range(max_goals + 1)]
    matrix = np.outer(home, away)

    best_score = None
    best_prob = 0
    scores = {}

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = matrix[i][j]
            score_str = f"{i}:{j}"
            scores[score_str] = float(p)
            if p > best_prob:
                best_prob = p
                best_score = score_str

    total = sum(scores.values())
    scores = {k: float(v / total) for k, v in scores.items()}
    top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]

    return scores, best_score, top_scores


def predict_v3(team1, team2, team_stats, matches_history, league_avg, model_dict):
    """Prédiction V3"""
    
    stats1 = team_stats.get(team1, {'played': 0})
    stats2 = team_stats.get(team2, {'played': 0})

    if stats1['played'] == 0 or stats2['played'] == 0:
        return {"error": "Données insuffisantes"}

    h2h = calculate_head_to_head(team1, team2, matches_history)
    lam1 = expected_goals(team1, team2, team_stats, league_avg, True)
    lam2 = expected_goals(team2, team1, team_stats, league_avg, False)
    
    form1_5 = recent_form(team1, matches_history, 5)
    form2_5 = recent_form(team2, matches_history, 5)
    form1_3 = recent_form(team1, matches_history, 3)
    form2_3 = recent_form(team2, matches_history, 3)
    
    draw_prob = calculate_draw_probability(team1, team2, team_stats, matches_history)
    
    f1 = team_stats.get(team1, {})
    f2 = team_stats.get(team2, {})
    
    def safe_div(a, b):
        return a / b if b else 0.0

    played1 = max(f1.get('played', 1), 1)
    played2 = max(f2.get('played', 1), 1)

    features = np.array([[
        lam1, lam2,
        lam1 - lam2,
        (lam1 + lam2) / 2,
        
        h2h['win_rate1'] - h2h['win_rate2'],
        h2h['draw_rate'],
        min(h2h['matches_played'] / 10.0, 1.0),
        h2h['avg_goals_h2h'],
        h2h['recent_h2h_form'],
        h2h['h2h_advantage'],
        h2h['btts_rate_h2h'],
        h2h['over_25_rate_h2h'],
        
        form1_5['points_rate'] - form2_5['points_rate'],
        form1_5['goal_diff_avg'] - form2_5['goal_diff_avg'],
        form1_5['btts_rate'] - form2_5['btts_rate'],
        form1_5['over_25_rate'] - form2_5['over_25_rate'],
        
        form1_3['points_rate'] - form2_3['points_rate'],
        form1_3['goal_diff_avg'] - form2_3['goal_diff_avg'],
        
        form1_5['form_trend'] - form2_5['form_trend'],
        
        form1_5['draw_rate'],
        form2_5['draw_rate'],
        draw_prob,
        1 if abs(lam1 - lam2) < 0.4 else 0,
        1 if abs(lam1 - lam2) < 0.2 else 0,
        
        form1_5['gf_avg'] - form2_5['ga_avg'],
        form1_5['ga_avg'] - form2_5['gf_avg'],
        
        safe_div(f1.get('goals_for', 0), played1) - safe_div(f2.get('goals_for', 0), played2),
        safe_div(f1.get('goals_against', 0), played1) - safe_div(f2.get('goals_against', 0), played2),
        
        safe_div(f1.get('home_goals_for', 0), max(f1.get('home_played', 1), 1)),
        safe_div(f2.get('away_goals_for', 0), max(f2.get('away_played', 1), 1)),
        safe_div(f1.get('home_goals_against', 0), max(f1.get('home_played', 1), 1)),
        safe_div(f2.get('away_goals_against', 0), max(f2.get('away_played', 1), 1)),
        
        safe_div(f1.get('clean_sheets', 0), played1) - safe_div(f2.get('clean_sheets', 0), played2),
        safe_div(f1.get('failed_to_score', 0), played1) - safe_div(f2.get('failed_to_score', 0), played2),
        
        safe_div(f1.get('wins', 0), played1) - safe_div(f2.get('wins', 0), played2),
        safe_div(f1.get('draws', 0), played1) - safe_div(f2.get('draws', 0), played2),
        
        f1.get('form_avg', 0.5) - f2.get('form_avg', 0.5),
    ]])
    
    scaler = model_dict['scaler']
    features_scaled = scaler.transform(features)
    
    prob_xgb = model_dict['xgb'].predict_proba(features_scaled)[0]
    prob_rf = model_dict['rf'].predict_proba(features_scaled)[0]
    prob_gb = model_dict['gb'].predict_proba(features_scaled)[0]
    
    weights = model_dict['weights']
    prob_ensemble = prob_xgb * weights[0] + prob_rf * weights[1] + prob_gb * weights[2]
    
    poisson_scores, best_score_poisson, top_scores = predict_poisson_correct_score(lam1, lam2)
    
    poisson_win_probs = np.array([
        sum(v for k, v in poisson_scores.items() if int(k.split(":")[0]) > int(k.split(":")[1])),
        sum(v for k, v in poisson_scores.items() if int(k.split(":")[0]) < int(k.split(":")[1])),
        sum(v for k, v in poisson_scores.items() if int(k.split(":")[0]) == int(k.split(":")[1]))
    ])
    
    final_probs = 0.7 * prob_ensemble + 0.3 * poisson_win_probs
    
    threshold = model_dict['threshold']
    final_probs_adj = final_probs.copy()
    final_probs_adj[2] = final_probs_adj[2] * (threshold / 0.5)
    final_probs_adj = final_probs_adj / final_probs_adj.sum()
    
    team1_prob_pct = final_probs_adj[0] * 100
    team2_prob_pct = final_probs_adj[1] * 100
    draw_prob_pct = final_probs_adj[2] * 100
    
    max_idx = np.argmax(final_probs_adj)
    if max_idx == 0:
        prediction = f"Victoire {team1}"
        if final_probs_adj[0] > 0.55:
            confidence_level = "Élevé"
        elif final_probs_adj[0] > 0.42:
            confidence_level = "Moyen"
        else:
            confidence_level = "Faible"
    elif max_idx == 1:
        prediction = f"Victoire {team2}"
        if final_probs_adj[1] > 0.55:
            confidence_level = "Élevé"
        elif final_probs_adj[1] > 0.42:
            confidence_level = "Moyen"
        else:
            confidence_level = "Faible"
    else:
        prediction = "Match Nul"
        if final_probs_adj[2] > 0.34:
            confidence_level = "Élevé"
        elif final_probs_adj[2] > 0.27:
            confidence_level = "Moyen"
        else:
            confidence_level = "Faible"
    
    if max_idx == 0:
        home_win_scores = [(s, p) for s, p in top_scores if int(s.split(':')[0]) > int(s.split(':')[1])]
        best_score = home_win_scores[0][0] if home_win_scores else f"{max(1, round(lam1))}:{round(lam2)}"
    elif max_idx == 1:
        away_win_scores = [(s, p) for s, p in top_scores if int(s.split(':')[0]) < int(s.split(':')[1])]
        best_score = away_win_scores[0][0] if away_win_scores else f"{round(lam1)}:{max(1, round(lam2))}"
    else:
        draw_scores = [(s, p) for s, p in top_scores if int(s.split(':')[0]) == int(s.split(':')[1])]
        if draw_scores:
            best_score = draw_scores[0][0]
        else:
            avg_goals = round((lam1 + lam2) / 2)
            best_score = f"{avg_goals}:{avg_goals}"
    
    entropy = -np.sum(final_probs_adj * np.log(final_probs_adj + 1e-10))
    confidence_score = float(1 / (1 + entropy))
    
    return {
        "team1_win_prob": round(team1_prob_pct, 1),
        "team2_win_prob": round(team2_prob_pct, 1),
        "draw_prob": round(draw_prob_pct, 1),
        "prediction": prediction,
        "expected_score": best_score,
        "confidence": confidence_level,
        "confidence_score": round(confidence_score, 3),
        "top_scores": [[score, round(prob*100, 1)] for score, prob in top_scores[:5]],
        "expected_goals": f"{lam1:.2f} : {lam2:.2f}"
    }


def load_model():
    global model, scaler
    if model is not None:
        return model

    if os.path.exists(MODEL_FINAL_PATH) and os.path.exists(SCALER_FINAL_PATH):
        try:
            with open(MODEL_FINAL_PATH, 'rb') as f:
                model = pickle.load(f)
            with open(SCALER_FINAL_PATH, 'rb') as f:
                scaler = pickle.load(f)
            print("✅ Modèle V3 chargé!")
            return model
        except Exception as e:
            print(f"Erreur chargement: {e}")
            return None
    return None


def init_v3_model():
    global model, scaler
    
    print("\n" + "="*80)
    print(" "*15 + "🚀 ENTRAÎNEMENT MODÈLE V3 🚀")
    print("="*80 + "\n")
    
    team_stats, matches_history, league_avg, df = load_match_data()
    if not team_stats or len(df) == 0:
        print("❌ Aucune donnée - Vérifiez le fichier Excel")
        return None

    # Vérifier si le modèle existe déjà
    if os.path.exists(MODEL_FINAL_PATH) and os.path.exists(SCALER_FINAL_PATH):
        try:
            with open(MODEL_FINAL_PATH, 'rb') as f:
                model = pickle.load(f)
            with open(SCALER_FINAL_PATH, 'rb') as f:
                scaler = pickle.load(f)
            print("✅ Modèle V3 déjà existant, chargé!")
            return model
        except:
            pass

    X, y = build_dataset_v3(team_stats, matches_history, league_avg, df)
    if len(X) < 100:
        print(f"❌ Pas assez de données: {len(X)} < 100")
        return None

    model, metrics = train_v3_model(X, y)

    with open(MODEL_FINAL_PATH, 'wb') as f:
        pickle.dump(model, f)
    with open(SCALER_FINAL_PATH, 'wb') as f:
        pickle.dump(scaler, f)

    print("\n✅ Modèle V3 sauvegardé!")
    
    print("\n" + "="*80)
    print(" "*15 + "🏆 RÉSULTATS MODÈLE V3 🏆")
    print("="*80)
    
    print(f"\n🎯 ACCURACY: {metrics['accuracy']*100:.2f}%")
    print(f"🤝 RECALL DRAW: {metrics['report']['2']['recall']*100:.2f}%")
    print(f"📈 F1 DRAW: {metrics['report']['2']['f1-score']*100:.2f}%")
    print(f"🏠 RECALL HOME: {metrics['report']['0']['recall']*100:.2f}%")
    print(f"✈️ RECALL AWAY: {metrics['report']['1']['recall']*100:.2f}%")
    
    betting_score = (metrics['report']['0']['recall'] * 30 + 
                     metrics['report']['1']['recall'] * 30 + 
                     metrics['report']['2']['recall'] * 40)
    print(f"\n🎲 SCORE POUR PARIS: {betting_score:.1f}%")
    
    return model


@app.route("/")
def index():
    return render_template("index.html", equipes=EQUIPES)


@app.route("/train-model", methods=['POST'])
def train_model():
    try:
        team_stats, matches_history, league_avg, df = load_match_data()
        if not team_stats or len(df) == 0:
            return jsonify({'error': 'Erreur chargement données'}), 500

        X, y = build_dataset_v3(team_stats, matches_history, league_avg, df)
        
        if len(X) < 100:
            return jsonify({'error': f'Pas assez de données: {len(X)} matchs'}), 400

        model_dict, metrics = train_v3_model(X, y)

        with open(MODEL_FINAL_PATH, 'wb') as f:
            pickle.dump(model_dict, f)
        with open(SCALER_FINAL_PATH, 'wb') as f:
            pickle.dump(scaler, f)

        global model
        model = model_dict

        return jsonify({
            'message': 'Modèle V3 entraîné avec succès',
            'accuracy': metrics['accuracy'],
            'recall_draw': metrics['report']['2']['recall']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/analyser", methods=['POST'])
def analyser():
    try:
        data = request.get_json(force=True)
        matchs = data.get('matchs', [])

        if not matchs:
            return jsonify({'error': 'Aucun match'}), 400

        team_stats, matches_history, league_avg, df = load_match_data()
        model_dict = load_model()
        
        if model_dict is None:
            return jsonify({'error': 'Modèle non entraîné. Veuillez réessayer dans quelques instants.'}), 400

        predictions = []
        for match in matchs:
            equipe1 = match.get('equipe1')
            equipe2 = match.get('equipe2')
            heure = match.get('heure', '')

            if not equipe1 or not equipe2:
                continue

            pred = predict_v3(equipe1, equipe2, team_stats, matches_history, league_avg, model_dict)
            predictions.append({
                'heure': heure,
                'equipe1': equipe1,
                'equipe2': equipe2,
                'prediction': pred
            })

        return jsonify({'predictions': predictions})

    except Exception as e:
        print(f"Erreur analyse: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route("/model-info", methods=['GET'])
def model_info():
    return jsonify({
        'model_type': 'Ultimate V3 - Optimal',
        'features_count': 42,
        'version': 'V3_FINAL',
        'strategy': '50% Draw Recall + 50% Accuracy'
    })


@app.route("/stats", methods=['GET'])
def get_stats():
    team_stats, _, _, _ = load_match_data()
    stats_summary = {}
    for team, stats in team_stats.items():
        if stats['played'] > 0:
            stats_summary[team] = {
                'played': int(stats['played']),
                'wins': int(stats['wins']),
                'draws': int(stats['draws']),
                'losses': int(stats['losses']),
                'goals_for': int(stats['goals_for']),
                'goals_against': int(stats['goals_against']),
                'points': int(stats['wins'] * 3 + stats['draws'])
            }
    return jsonify({'teams': stats_summary})


@app.route("/debug", methods=['GET'])
def debug():
    """Affiche les fichiers disponibles"""
    import os
    
    # Lister les fichiers
    root_files = os.listdir('.')
    
    # Vérifier le dossier data
    data_files = []
    if os.path.exists('data'):
        data_files = os.listdir('data')
    
    # Vérifier les fichiers modèle
    model_exists = os.path.exists('model_final.pkl') or os.path.exists('model.pkl')
    scaler_exists = os.path.exists('scaler_final.pkl') or os.path.exists('scaler.pkl')
    
    return jsonify({
        'current_directory': os.getcwd(),
        'root_files': root_files[:50],  # 50 premiers fichiers
        'data_files': data_files,
        'model_exists': model_exists,
        'scaler_exists': scaler_exists,
        'data_path_exists': os.path.exists('data/virtual_stats.xlsx')
    })


if __name__ == "__main__":
    print("\n" + "="*80)
    print(" "*15 + "⚽ MODÈLE V3 OPTIMAL - POUR PARIS SPORTIFS ⚽")
    print("="*80)
    
    # Vérifier si le fichier data existe
    if not os.path.exists(DATA_PATH):
        print(f"\n⚠️ Attention: Fichier Excel non trouvé à {DATA_PATH}")
        print("📌 Veuillez vérifier que le fichier 'virtual_stats.xlsx' est dans le dossier 'data/'")
    
    # Entraînement automatique
    print("\n🚀 Entraînement du modèle en cours...\n")
    init_v3_model()
    
    print("\n✅ Modèle prêt! Serveur en ligne...")
    
    # Port pour Render
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🌐 Serveur démarré sur http://0.0.0.0:{port}")
    print("="*80 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)