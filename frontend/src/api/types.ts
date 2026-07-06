export interface UserMe {
  id: number;
  username: string;
  email: string;
  profile: string;
  permissions: string[];
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Team {
  id: number;
  name: string;
  display_name: string;
  code: string;
  confederation: string;
  group_label: string | null;
  is_host: boolean;
  elo: number;
}

export interface Prediction {
  model_name: string;
  p_home: number;
  p_draw: number;
  p_away: number;
  exp_home_goals: number;
  exp_away_goals: number;
  top_scoreline: string;
}

export interface TeamRef {
  id: number;
  name: string;
  display_name: string;
  code: string;
}

export interface Match {
  id: number;
  stage: string;
  group_label: string | null;
  slot: string | null;
  home_team: TeamRef | null;
  away_team: TeamRef | null;
  scheduled_at: string | null;
  venue: string;
  is_neutral: boolean;
  status: string;
  home_score: number | null;
  away_score: number | null;
  winner_team_id: number | null;
  prediction: Prediction | null;
}

export interface TeamProb {
  team: string;
  display_name: string;
  code: string;
  confederation: string;
  group_label: string | null;
  p_group_winner: number;
  p_group_runner_up: number;
  p_advance: number;
  p_r16: number;
  p_qf: number;
  p_sf: number;
  p_final: number;
  p_winner: number;
}

export interface Simulation {
  id: number;
  created_at: string;
  runs: number;
  model_name: string;
  notes: string;
  probs: TeamProb[];
}

export interface Permission {
  key: string;
  description: string;
}

export interface Profile {
  id: number;
  name: string;
  description: string;
  max_users: number | null;
  is_system: boolean;
  permissions: string[];
  user_count: number;
}

export interface User {
  id: number;
  username: string;
  email: string;
  profile: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface BetMarket {
  id: string;
  category: string;
  label: string;
  prob: number;
  odds: number;
}

export interface MatchMarkets {
  match_id: number;
  home: string;
  away: string;
  status: string;
  exp_goals_home: number;
  exp_goals_away: number;
  markets: BetMarket[];
}

export interface CombineResult {
  prob: number;
  odds: number;
}

export interface EvolutionPoint {
  run_id: number;
  created_at: string;
  p_advance: number;
  p_winner: number;
  p_final: number;
}

export interface BayesStrength {
  team: string;
  display_name: string;
  code: string;
  confederation: string;
  group_label: string | null;
  att: number;
  att_std: number;
  defense: number;
  def_std: number;
  overall: number;
  overall_lo: number;
  overall_hi: number;
}
