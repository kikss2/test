package com.example.basketball_project.model;

import java.util.List;

public class SportsApiResponse {
    private int success;
    private List<Result> result;

    // Getters and setters
    public int getSuccess() {
        return success;
    }

    public void setSuccess(int success) {
        this.success = success;
    }

    public List<Result> getResult() {
        return result;
    }

    public void setResult(List<Result> result) {
        this.result = result;
    }

    public static class Result {
        private int game_id;
        private String event_date;
        private String event_time;
        private String event_home_team;
        private String event_away_team;
        private String event_final_result;
        private int home_team_key;
        private int away_team_key;

        // Getters and setters
        public int getGame_id() {
            return game_id;
        }

        public void setGame_id(int game_id) {
            this.game_id = game_id;
        }

        public String getEvent_date() {
            return event_date;
        }

        public void setEvent_date(String event_date) {
            this.event_date = event_date;
        }

        public String getEvent_time() {
            return event_time;
        }

        public void setEvent_time(String event_time) {
            this.event_time = event_time;
        }

        public String getEvent_home_team() {
            return event_home_team;
        }

        public void setEvent_home_team(String event_home_team) {
            this.event_home_team = event_home_team;
        }

        public String getEvent_away_team() {
            return event_away_team;
        }

        public void setEvent_away_team(String event_away_team) {
            this.event_away_team = event_away_team;
        }

        public String getEvent_final_result() {
            return event_final_result;
        }

        public void setEvent_final_result(String event_final_result) {
            this.event_final_result = event_final_result;
        }

        public int getHome_team_key() {
            return home_team_key;
        }

        public void setHome_team_key(int home_team_key) {
            this.home_team_key = home_team_key;
        }

        public int getAway_team_key() {
            return away_team_key;
        }
    }
}