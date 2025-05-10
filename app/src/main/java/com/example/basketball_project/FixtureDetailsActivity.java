package com.example.basketball_project;

import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.AsyncTask;
import android.os.Bundle;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TableLayout;
import android.widget.TableRow;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.android.volley.DefaultRetryPolicy;
import com.android.volley.Request;
import com.android.volley.RequestQueue;
import com.android.volley.toolbox.JsonObjectRequest;
import com.android.volley.toolbox.StringRequest;
import com.android.volley.toolbox.Volley;
import com.example.basketball_project.model.SportsApiResponse;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class FixtureDetailsActivity extends AppCompatActivity {

    private static final String API_KEY = "5f9a501ea6e90dc4acd45a505a7e056f125437f63a73d202023fce0a227ac436";
    private static final int LEBANON_LEAGUE_ID = 10290;

    private ImageView ivHomeTeamLogo, ivAwayTeamLogo;
    private TextView tvHomeTeamName, tvAwayTeamName, tvScore, tvMatchStatus;
    private TextView tvHomeTeam1stQ, tvAwayTeam1stQ, tvHomeTeam2ndQ, tvAwayTeam2ndQ,
            tvHomeTeam3rdQ, tvAwayTeam3rdQ, tvHomeTeam4thQ, tvAwayTeam4thQ;
    private TextView tabPlayers, tabScores, tabStats;
    private LinearLayout playersSection, scoresSection, statsSection;
    private View scoreBar1stQHome, scoreBar1stQAway, scoreBar2ndQHome, scoreBar2ndQAway,
            scoreBar3rdQHome, scoreBar3rdQAway, scoreBar4thQHome, scoreBar4thQAway;
    private int eventKey;
    private String eventDate;

    private int homeTeamId;
    private int awayTeamId;


    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_fixture_details);

        // Initialize views
        initViews();

        // Set click listeners for tabs
        setupTabListeners();
        setInitialTabState();
        // Get intent data
        Intent intent = getIntent();
        this.eventDate = intent.getStringExtra("event_date");
        eventKey = intent.getIntExtra("event_key", -1);

        if (eventKey == -1) {
            Toast.makeText(this, "❌ No event key provided!", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        this.homeTeamId = intent.getIntExtra("home_team_key", 0);
        this.awayTeamId = intent.getIntExtra("away_team_key", 0);
        Log.d("kharrrra", " heyyy " + homeTeamId + "man " + awayTeamId);

        fetchAndDisplayH2HData(homeTeamId,awayTeamId);
        loadFixtureDetails();

        ImageButton btnBack = findViewById(R.id.btnBack);
        btnBack.setOnClickListener(v -> {
            finish();
        });
    }

    private void fetchAndDisplayH2HData(int homeTeamId, int awayTeamId) {
        String h2hUrl = "https://apiv2.allsportsapi.com/basketball/?met=H2H" +
                "&firstTeamId=" + homeTeamId +
                "&secondTeamId=" + awayTeamId +
                "&leagueId=" + LEBANON_LEAGUE_ID +
                "&APIkey=" + API_KEY;

        Log.d("H2H_DEBUG", "Request URL: " + h2hUrl);

        RequestQueue queue = Volley.newRequestQueue(this);
        JsonObjectRequest h2hRequest = new JsonObjectRequest(
                Request.Method.GET, h2hUrl, null,
                response -> {
                    try {
                        Log.d("H2H_DEBUG", "Raw response: " + response.toString());

                        // First check if response has the expected structure
                        if (!response.has("success")) {
                            throw new JSONException("Response missing 'success' field");
                        }

                        if (response.getInt("success") == 1) {
                            if (!response.has("result")) {
                                throw new JSONException("Response missing 'result' field");
                            }

                            JSONObject result = response.getJSONObject("result");
                            if (!result.has("H2H")) {
                                throw new JSONException("Response missing 'H2H' field");
                            }

                            JSONArray h2hMatches = result.getJSONArray("H2H");
                            Log.d("H2H_DEBUG", "Found " + h2hMatches.length() + " matches");

                            // Process matches...
                            int[] wins = calculateWins(h2hMatches);
                            runOnUiThread(() -> updateH2HUI(wins[0], wins[1], h2hMatches));

                        } else {
                            Log.d("H2H_DEBUG", "API returned success=0");
                            runOnUiThread(() ->
                                    Toast.makeText(this, "No H2H data available", Toast.LENGTH_SHORT).show());
                        }
                    } catch (Exception e) {
                        Log.e("H2H_DEBUG", "Error parsing response: " + e.getMessage());
                        Log.e("H2H_DEBUG", "Response was: " + response.toString());
                        runOnUiThread(() ->
                                Toast.makeText(this, "Invalid data format", Toast.LENGTH_SHORT).show());
                    }
                },
                error -> {
                    String errorMsg = "Network error";
                    if (error.networkResponse != null) {
                        errorMsg += " (Status: " + error.networkResponse.statusCode + ")";
                        try {
                            String responseBody = new String(error.networkResponse.data);
                            Log.e("H2H_DEBUG", "Error response: " + responseBody);
                        } catch (Exception e) {
                            Log.e("H2H_DEBUG", "Couldn't parse error response");
                        }
                    }
                    Log.e("H2H_DEBUG", errorMsg, error);

                }
        );

        // Set timeout policy
        h2hRequest.setRetryPolicy(new DefaultRetryPolicy(
                15000, // 15 seconds timeout
                DefaultRetryPolicy.DEFAULT_MAX_RETRIES,
                DefaultRetryPolicy.DEFAULT_BACKOFF_MULT));

        queue.add(h2hRequest);
    }

    private int[] calculateWins(JSONArray h2hMatches) throws JSONException {
        int homeWins = 0;
        int awayWins = 0;

        for (int i = 0; i < h2hMatches.length(); i++) {
            JSONObject match = h2hMatches.getJSONObject(i);

            // Get the team keys and scores
            int matchHomeTeamId = match.getInt("home_team_key");
            int matchAwayTeamId = match.getInt("away_team_key");
            String score = match.getString("event_final_result");

            // Parse the scores
            String[] scores = score.split(" - ");
            if (scores.length == 2) {
                try {
                    int homeScore = Integer.parseInt(scores[0].trim());
                    int awayScore = Integer.parseInt(scores[1].trim());

                    // Determine which team is "our" home team in this context
                    if (matchHomeTeamId == homeTeamId) {
                        // Current match home team is our reference home team
                        if (homeScore > awayScore) {
                            homeWins++;
                        } else if (awayScore > homeScore) {
                            awayWins++;
                        }
                    } else if (matchAwayTeamId == homeTeamId) {
                        // Current match away team is our reference home team
                        if (awayScore > homeScore) {
                            homeWins++;
                        } else if (homeScore > awayScore) {
                            awayWins++;
                        }
                    }
                } catch (NumberFormatException e) {
                    Log.e("H2H", "Invalid score format: " + score, e);
                }
            }
        }

        return new int[]{homeWins, awayWins};
    }


    private void updateH2HUI(int homeWins, int awayWins, JSONArray matches) {
        try {
            // 1. Update the win counts
            TextView tvHomeWins = findViewById(R.id.tvHomeWins);
            TextView tvAwayWins = findViewById(R.id.tvAwayWins);
            tvHomeWins.setText(String.valueOf(homeWins));
            tvAwayWins.setText(String.valueOf(awayWins));

            // 2. Update the matches list
            LinearLayout matchesContainer = findViewById(R.id.h2hMatchesContainer);
            matchesContainer.removeAllViews(); // Clear existing views

            // 3. Add each match to the container (limit to 5)
            int count = Math.min(matches.length(), 5);
            for (int i = 0; i < count; i++) {
                addMatchItem(matchesContainer, matches.getJSONObject(i));
            }

        } catch (JSONException e) {
            Log.e("H2H", "Error updating UI", e);
        }
    }


    private void addMatchItem(LinearLayout container, JSONObject match) throws JSONException {
        View matchItem = LayoutInflater.from(this).inflate(R.layout.item_h2h_match, container, false);

        // Set match data
        TextView tvDate = matchItem.findViewById(R.id.tvMatchDate);
        tvDate.setText(formatDate(match.getString("event_date")));

        TextView tvHomeTeam = matchItem.findViewById(R.id.tvHomeTeam);
        TextView tvAwayTeam = matchItem.findViewById(R.id.tvAwayTeam);
        tvHomeTeam.setText(match.getString("event_home_team"));
        tvAwayTeam.setText(match.getString("event_away_team"));

        String[] scores = match.getString("event_final_result").split(" - ");
        TextView tvHomeScore = matchItem.findViewById(R.id.tvHomeScore);
        TextView tvAwayScore = matchItem.findViewById(R.id.tvAwayScore);
        tvHomeScore.setText(scores[0].trim());
        tvAwayScore.setText(scores[1].trim());

        // Make the entire match item clickable
        matchItem.setOnClickListener(v -> {
            try {
                // Get all needed data from the clicked match
                int eventKey = match.getInt("event_key");
                String eventDate = match.getString("event_date");
                int homeTeamKey = match.getInt("home_team_key");
                int awayTeamKey = match.getInt("away_team_key");

                // Launch the same activity with new data
                Intent intent = new Intent(FixtureDetailsActivity.this, FixtureDetailsActivity.class);
                intent.putExtra("event_key", eventKey);
                intent.putExtra("event_date", eventDate);
                intent.putExtra("home_team_key", homeTeamKey);
                intent.putExtra("away_team_key", awayTeamKey);

                startActivity(intent);
            } catch (JSONException e) {
                Log.e("MatchClick", "Error handling match click", e);
            }
        });

        container.addView(matchItem);
    }

    private String formatDate(String inputDate) {
        try {
            SimpleDateFormat inputFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
            SimpleDateFormat outputFormat = new SimpleDateFormat("MMM d, yyyy", Locale.getDefault());
            Date date = inputFormat.parse(inputDate);
            return outputFormat.format(date);
        } catch (ParseException e) {
            return inputDate;
        }
    }



    private void initViews() {
        ivHomeTeamLogo = findViewById(R.id.ivHomeTeamLogo);
        ivAwayTeamLogo = findViewById(R.id.ivAwayTeamLogo);
        tvHomeTeamName = findViewById(R.id.tvHomeTeamName);
        tvAwayTeamName = findViewById(R.id.tvAwayTeamName);
        tvScore = findViewById(R.id.tvScore);
        tvMatchStatus = findViewById(R.id.tvMatchStatus);

        // Initialize quarter score views
        tvHomeTeam1stQ = findViewById(R.id.tvHomeTeam1stQ);
        tvAwayTeam1stQ = findViewById(R.id.tvAwayTeam1stQ);
        tvHomeTeam2ndQ = findViewById(R.id.tvHomeTeam2ndQ);
        tvAwayTeam2ndQ = findViewById(R.id.tvAwayTeam2ndQ);
        tvHomeTeam3rdQ = findViewById(R.id.tvHomeTeam3rdQ);
        tvAwayTeam3rdQ = findViewById(R.id.tvAwayTeam3rdQ);
        tvHomeTeam4thQ = findViewById(R.id.tvHomeTeam4thQ);
        tvAwayTeam4thQ = findViewById(R.id.tvAwayTeam4thQ);

        // Initialize score bars
        scoreBar1stQHome = findViewById(R.id.scoreBar1stQHome);
        scoreBar1stQAway = findViewById(R.id.scoreBar1stQAway);
        scoreBar2ndQHome = findViewById(R.id.scoreBar2ndQHome);
        scoreBar2ndQAway = findViewById(R.id.scoreBar2ndQAway);
        scoreBar3rdQHome = findViewById(R.id.scoreBar3rdQHome);
        scoreBar3rdQAway = findViewById(R.id.scoreBar3rdQAway);
        scoreBar4thQHome = findViewById(R.id.scoreBar4thQHome);
        scoreBar4thQAway = findViewById(R.id.scoreBar4thQAway);

        tabPlayers = findViewById(R.id.tabPlayers);
        tabScores = findViewById(R.id.tabScores);
        tabStats = findViewById(R.id.tabStats);

        playersSection = findViewById(R.id.playersSection);
        scoresSection = findViewById(R.id.scoresSection);
        statsSection = findViewById(R.id.statsSection);
    }
    private void setInitialTabState() {
        // Set Scores tab as active by default
        tabScores.performClick();

        // Or alternatively:
        playersSection.setVisibility(View.GONE);
        scoresSection.setVisibility(View.VISIBLE);
        statsSection.setVisibility(View.GONE);

        tabPlayers.setTextColor(getResources().getColor(R.color.white));
        tabScores.setTextColor(getResources().getColor(R.color.orange));
        tabStats.setTextColor(getResources().getColor(R.color.white));
    }


    private void setupTabListeners() {
        tabPlayers.setOnClickListener(v -> {
            playersSection.setVisibility(View.VISIBLE);
            scoresSection.setVisibility(View.GONE);
            statsSection.setVisibility(View.GONE);

            tabPlayers.setTextColor(getResources().getColor(R.color.orange));
            tabScores.setTextColor(getResources().getColor(android.R.color.white));
            tabStats.setTextColor(getResources().getColor(android.R.color.white));
            fetchAndShowStandings();

        });

        tabScores.setOnClickListener(v -> {
            playersSection.setVisibility(View.GONE);
            scoresSection.setVisibility(View.VISIBLE);
            statsSection.setVisibility(View.GONE);

            tabPlayers.setTextColor(getResources().getColor(android.R.color.white));
            tabScores.setTextColor(getResources().getColor(R.color.orange));
            tabStats.setTextColor(getResources().getColor(android.R.color.white));
        });

        tabStats.setOnClickListener(v -> {
            playersSection.setVisibility(View.GONE);
            scoresSection.setVisibility(View.GONE);
            statsSection.setVisibility(View.VISIBLE);

            tabPlayers.setTextColor(getResources().getColor(android.R.color.white));
            tabScores.setTextColor(getResources().getColor(android.R.color.white));
            tabStats.setTextColor(getResources().getColor(R.color.orange));
        });
    }

    private void loadFixtureDetails() {
        String apiUrl = "https://apiv2.allsportsapi.com/basketball/?met=Fixtures" +
                "&leagueId=" + LEBANON_LEAGUE_ID +
                "&from=" + eventDate +
                "&to=" + eventDate +
                "&APIkey=" + API_KEY;

        new FetchFixtureDetailsTask().execute(apiUrl);
    }

    private class FetchFixtureDetailsTask extends AsyncTask<String, Void, String> {
        @Override
        protected String doInBackground(String... urls) {
            try {
                URL url = new URL(urls[0]);
                HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;

                while ((line = reader.readLine()) != null) {
                    response.append(line);
                }

                reader.close();
                return response.toString();
            } catch (Exception e) {
                e.printStackTrace();
                return null;
            }
        }

        @Override
        protected void onPostExecute(String result) {
            if (result == null) {
                Toast.makeText(FixtureDetailsActivity.this, "❌ Failed to load fixture details.", Toast.LENGTH_SHORT).show();
                return;
            }

            try {
                JSONObject jsonResponse = new JSONObject(result);
                if (jsonResponse.getInt("success") != 1) {
                    Toast.makeText(FixtureDetailsActivity.this, "📭 No data available.", Toast.LENGTH_SHORT).show();
                    return;
                }

                JSONArray fixtures = jsonResponse.getJSONArray("result");

                for (int i = 0; i < fixtures.length(); i++) {
                    JSONObject fixture = fixtures.getJSONObject(i);
                    int key = fixture.getInt("event_key");

                    if (key == eventKey) {
                        // Set team names and  score
                        String homeTeam = fixture.getString("event_home_team");
                        String awayTeam = fixture.getString("event_away_team");
                        String finalResult = fixture.optString("event_final_result", "N/A");
                        String status = fixture.getString("event_status");

                        tvHomeTeamName.setText(homeTeam);
                        tvAwayTeamName.setText(awayTeam);
                        tvScore.setText(finalResult);
                        tvMatchStatus.setText(status);

                        // Load team logos (placeholder implementation)
                        ivHomeTeamLogo.setImageResource(R.drawable.img);
                        ivAwayTeamLogo.setImageResource(R.drawable.img_1);

                        // Update quarter scores with visual bars
                        updateQuarterScores(fixture);
                        return;
                    }
                }

                Toast.makeText(FixtureDetailsActivity.this, "❓ Fixture not found for the selected key.", Toast.LENGTH_SHORT).show();

            } catch (Exception e) {
                Toast.makeText(FixtureDetailsActivity.this, "⚠️ Error parsing fixture details.", Toast.LENGTH_SHORT).show();
                e.printStackTrace();
            }
        }
    }

    private void updateQuarterScores(JSONObject fixture) throws JSONException {
        if (fixture.has("scores")) {
            JSONObject scores = fixture.getJSONObject("scores");

            // Helper method to update each quarter
            updateQuarterScore(scores, "1stQuarter",
                    tvHomeTeam1stQ, tvAwayTeam1stQ,
                    scoreBar1stQHome, scoreBar1stQAway);

            updateQuarterScore(scores, "2ndQuarter",
                    tvHomeTeam2ndQ, tvAwayTeam2ndQ,
                    scoreBar2ndQHome, scoreBar2ndQAway);

            updateQuarterScore(scores, "3rdQuarter",
                    tvHomeTeam3rdQ, tvAwayTeam3rdQ,
                    scoreBar3rdQHome, scoreBar3rdQAway);

            updateQuarterScore(scores, "4thQuarter",
                    tvHomeTeam4thQ, tvAwayTeam4thQ,
                    scoreBar4thQHome, scoreBar4thQAway);
        }

    }


    private void fetchAndShowStandings() {
        String url = "https://apiv2.allsportsapi.com/basketball/?met=Standings&leagueId=10290&APIkey=5f9a501ea6e90dc4acd45a505a7e056f125437f63a73d202023fce0a227ac436";
        RequestQueue queue = Volley.newRequestQueue(this);

        JsonObjectRequest jsonObjectRequest = new JsonObjectRequest(
                Request.Method.GET, url, null,
                response -> {
                    Log.d("MainActivity", "API Response: " + response.toString());
                    try {
                        JSONObject result = response.getJSONObject("result");
                        JSONArray standings = result.getJSONArray("total");
                        showStandingsTable(standings);
                        Log.d("MainActivity", "Standings: " + standings.toString());
                    } catch (JSONException e) {
                        Log.e("MainActivity", "JSON parsing error: ", e);
                    }
                },
                error -> {
                    Log.e("API_ERROR", "Error fetching standings: " + error.getMessage());
                }
        );

        queue.add(jsonObjectRequest);
    }


    private void showStandingsTable(JSONArray standings) throws JSONException {
        TableLayout tableLayout = findViewById(R.id.tableStandings);
        tableLayout.removeViews(1, Math.max(0, tableLayout.getChildCount() - 1)); // Keep the header
        Log.d("MainActivity", "helllln: "  + " vs "  + " | Key: " + eventKey);

        for (int i = 0; i < standings.length(); i++) {
            JSONObject team = standings.getJSONObject(i);

            TableRow row = new TableRow(this);
            addTextToRow(row, team.getString("standing_team")); // "Team"
            addTextToRow(row, String.valueOf(team.getInt("standing_P"))); // "P"
            addTextToRow(row, String.valueOf(team.getInt("standing_W"))); // "W"
            addTextToRow(row, String.valueOf(team.getInt("standing_L"))); // "L"

            int points = team.getInt("standing_W") * 2; // You can adjust this logic
            addTextToRow(row, String.valueOf(points)); // "Pts"

            tableLayout.addView(row);
        }

        tableLayout.setVisibility(View.VISIBLE);
    }


    private void addTextToRow(TableRow row, String text) {
        TextView textView = new TextView(this);
        textView.setText(text);
        textView.setPadding(6, 6, 6, 6);
        row.addView(textView);
    }



    private void updateQuarterScore(JSONObject scores, String quarterKey,
                                    TextView tvHome, TextView tvAway,
                                    View barHome, View barAway) throws JSONException {
        if (scores.has(quarterKey)) {
            JSONArray quarter = scores.getJSONArray(quarterKey);
            JSONObject quarterScore = quarter.getJSONObject(0);

            int homeScore = Integer.parseInt(quarterScore.getString("score_home"));
            int awayScore = Integer.parseInt(quarterScore.getString("score_away"));
            int total = homeScore + awayScore;

            // Set scores text
            tvHome.setText(String.valueOf(homeScore));
            tvAway.setText(String.valueOf(awayScore));

            // Calculate bar weights
            float homeWeight = total > 0 ? (float) homeScore / total : 0.5f;
            float awayWeight = total > 0 ? (float) awayScore / total : 0.5f;

            // Update bar sizes
            LinearLayout.LayoutParams homeParams = (LinearLayout.LayoutParams) barHome.getLayoutParams();
            homeParams.weight = homeWeight;
            barHome.setLayoutParams(homeParams);

            LinearLayout.LayoutParams awayParams = (LinearLayout.LayoutParams) barAway.getLayoutParams();
            awayParams.weight = awayWeight;
            barAway.setLayoutParams(awayParams);
        }
    }
}