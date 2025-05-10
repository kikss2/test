package com.example.basketball_project;

import static androidx.core.content.ContextCompat.startActivity;

import android.app.DatePickerDialog;
import android.content.Intent;
import android.graphics.Color;
import android.os.AsyncTask;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import com.google.android.material.card.MaterialCardView;
import com.google.android.material.datepicker.MaterialDatePicker;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
import java.util.Locale;

public class MainActivity extends AppCompatActivity {

    private static final String API_KEY = "5f9a501ea6e90dc4acd45a505a7e056f125437f63a73d202023fce0a227ac436";
    private static final int LEBANON_LEAGUE_ID = 10290;

    private LinearLayout fixturesContainer, dateSelectorLayout;
    private Date currentSelectedDate;
    private final SimpleDateFormat apiDateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
    private final SimpleDateFormat displayDateFormat = new SimpleDateFormat("EEE d MMM", Locale.US);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        fixturesContainer = findViewById(R.id.llFixturesContainer);
        dateSelectorLayout = findViewById(R.id.llDateSelector);

        setupDateSelection();

        ImageButton btnCalendar = findViewById(R.id.btnCalendar);

        btnCalendar.setOnClickListener(v -> showDatePicker());
        currentSelectedDate = new Date();
        loadFixturesForDate(currentSelectedDate);

    }
    private void setupCalendarButton() {
        ImageButton btnCalendar = findViewById(R.id.btnCalendar);
        btnCalendar.setOnClickListener(v -> showDatePicker());
    }

    private void showDatePicker() {
        Calendar calendar = currentSelectedDate != null ?
                getCalendarFromDate(currentSelectedDate) : Calendar.getInstance();

        DatePickerDialog datePickerDialog = new DatePickerDialog(
                this,
                (view, year, month, dayOfMonth) -> {
                    // Create the selected date
                    Calendar selectedCal = Calendar.getInstance();
                    selectedCal.set(year, month, dayOfMonth);
                    Date selectedDate = selectedCal.getTime();

                    // Update UI and load fixtures for the exact selected date
                    currentSelectedDate = selectedDate;
                    loadFixturesForDate(selectedDate);

                    // Update the date selector to show the new range
                    updateDateSelectorAroundDate(selectedDate);
                },
                calendar.get(Calendar.YEAR),
                calendar.get(Calendar.MONTH),
                calendar.get(Calendar.DAY_OF_MONTH)
        );

        datePickerDialog.show();
    }

    private void updateDateSelectorAroundDate(Date centerDate) {
        dateSelectorLayout.removeAllViews(); // Clear existing dates

        Calendar calendar = Calendar.getInstance();
        calendar.setTime(centerDate);

        // Show 2 days before and after the selected date (total 5 days)
        for (int i = -2; i <= 2; i++) {
            Calendar tempCal = (Calendar) calendar.clone();
            tempCal.add(Calendar.DATE, i);
            Date date = tempCal.getTime();

            TextView tvDate = new TextView(this);
            tvDate.setText(displayDateFormat.format(date).toUpperCase());
            tvDate.setPadding(36, 20, 36, 20);

            // Highlight the selected date
            if (i == 0) {
                tvDate.setBackgroundResource(R.drawable.date_selected_background);
            } else {
                tvDate.setBackgroundResource(R.drawable.date_selector_background);
            }

            tvDate.setTextColor(getResources().getColor(android.R.color.white));
            tvDate.setTextSize(14);
            tvDate.setGravity(Gravity.CENTER);
            tvDate.setOnClickListener(v -> {
                updateDateSelection(tvDate);
                currentSelectedDate = date;
                loadFixturesForDate(date);
            });

            dateSelectorLayout.addView(tvDate);
        }
    }

    // Helper method to convert Date to Calendar
    private Calendar getCalendarFromDate(Date date) {
        Calendar cal = Calendar.getInstance();
        cal.setTime(date);
        return cal;
    }

    // Update your date selection UI (similar to your existing method)
    private void updateDateSelectionForCalendar(Date selectedDate) {
        // Clear previous selections
        for (int i = 0; i < dateSelectorLayout.getChildCount(); i++) {
            View child = dateSelectorLayout.getChildAt(i);
            if (child instanceof TextView) {
                child.setBackgroundResource(R.drawable.date_selector_background);
            }
        }

        // Find and highlight the matching date if it exists in your horizontal scroller
        String selectedDateStr = displayDateFormat.format(selectedDate);
        for (int i = 0; i < dateSelectorLayout.getChildCount(); i++) {
            View child = dateSelectorLayout.getChildAt(i);
            if (child instanceof TextView) {
                TextView tv = (TextView) child;
                if (tv.getText().toString().equalsIgnoreCase(selectedDateStr)) {
                    tv.setBackgroundResource(R.drawable.date_selector_background);
                    break;
                }
            }
        }
    }


    private void setupDateSelection() {
        Calendar calendar = Calendar.getInstance();

        for (int i = -2; i <= 2; i++) {
            Calendar tempCal = (Calendar) calendar.clone();
            tempCal.add(Calendar.DATE, i);
            Date date = tempCal.getTime();

            TextView tvDate = new TextView(this);
            tvDate.setText(displayDateFormat.format(date).toUpperCase());
            tvDate.setPadding(36, 20, 36, 20);
            tvDate.setBackgroundResource(R.drawable.date_selector_background);
            tvDate.setTextColor(getResources().getColor(android.R.color.white));
            tvDate.setTextSize(14);
            tvDate.setGravity(Gravity.CENTER);
            tvDate.setOnClickListener(v -> {
                updateDateSelection(tvDate);
                currentSelectedDate = date;
                loadFixturesForDate(date);
            });

            dateSelectorLayout.addView(tvDate);
        }
    }




    private void updateDateSelection(View selectedView) {
        for (int i = 0; i < dateSelectorLayout.getChildCount(); i++) {
            View child = dateSelectorLayout.getChildAt(i);
            child.setBackgroundResource(R.drawable.date_selector_background);
        }
        selectedView.setBackgroundResource(R.drawable.date_selected_background);
    }

    private void loadFixturesForDate(Date selectedDate) {
        String dateParam = apiDateFormat.format(selectedDate);
        String apiUrl = "https://apiv2.allsportsapi.com/basketball/?met=Fixtures" +
                "&leagueId=" + LEBANON_LEAGUE_ID +
                "&from=" + dateParam +
                "&to=" + dateParam +
                "&APIkey=" + API_KEY;

        Log.d("APIRequest", "Fetching fixtures from: " + apiUrl);
        new FetchFixturesTask().execute(apiUrl);
    }

    private class FetchFixturesTask extends AsyncTask<String, Void, String> {
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
            fixturesContainer.removeAllViews();

            if (result == null) {
                showError("❌ Failed to load fixtures. Check your internet.");
                return;
            }

            try {
                JSONObject jsonResponse = new JSONObject(result);
                if (jsonResponse.getInt("success") != 1) {
                    showError("📭 No data from API.");
                    return;
                }

                JSONArray fixtures = jsonResponse.getJSONArray("result");
                if (fixtures.length() == 0) {
                    showError("🕒 No matches for this date.");
                    return;
                }

                for (int i = 0; i < fixtures.length(); i++) {
                    JSONObject fixture = fixtures.getJSONObject(i);
                    Log.d("FixtureData", "Raw fixture data: " + fixture.toString());

                    // Safely extract event_key
                    int eventKey = -1;
                    try {
                        if (fixture.has("event_key")) {
                            Object keyObj = fixture.get("event_key");
                            if (keyObj instanceof Integer) {
                                eventKey = (Integer) keyObj;
                            } else if (keyObj instanceof String) {
                                eventKey = Integer.parseInt((String) keyObj);
                            } else {
                                Log.e("MainActivity", "Unknown event_key type: " + keyObj.getClass().getName());
                                continue; // Skip invalid key
                            }
                        } else {
                            Log.e("MainActivity", "No event_key in fixture");
                            continue; // Skip if no key
                        }
                    } catch (Exception e) {
                        Log.e("MainActivity", "Error parsing event_key", e);
                        continue; // Skip if parsing fails
                    }
                    String eventDate = fixture.optString("event_date", ""); // Use optString for safety
                    String eventTime = fixture.getString("event_time");
                    String homeTeam = fixture.getString("event_home_team");
                    String awayTeam = fixture.getString("event_away_team");
                    String finalResult = fixture.optString("event_final_result", "");
                    String status = fixture.optString("event_status", "");
                    int homeTeamKey = fixture.optInt("home_team_key", 0);
                    int awayTeamKey = fixture.optInt("away_team_key", 0);

                    String timeText;
                    try {
                        String eventDateTimeStr = fixture.getString("event_date") + " " + eventTime;
                        SimpleDateFormat utcFormat = new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US);
                        utcFormat.setTimeZone(java.util.TimeZone.getTimeZone("UTC"));

                        Date utcDate = utcFormat.parse(eventDateTimeStr);
                        SimpleDateFormat localFormat = new SimpleDateFormat("hh:mm a", Locale.getDefault());
                        localFormat.setTimeZone(java.util.TimeZone.getDefault());

                        timeText = localFormat.format(utcDate);
                    } catch (Exception e) {
                        timeText = eventTime;
                    }

                    if (!finalResult.isEmpty() && !finalResult.equals("-")) {
                        timeText += " | Final: " + finalResult;
                    } else if (!status.isEmpty()) {
                        timeText += " | " + status;
                    }

                    createFixtureCard(homeTeam, awayTeam, timeText, eventKey, eventDate, homeTeamKey, awayTeamKey);
                }

            } catch (Exception e) {
                showError(" No games today.");
                e.printStackTrace();
            }
        }

        private void showError(String message) {
            TextView errorView = new TextView(MainActivity.this);
            errorView.setText(message);
            errorView.setTextSize(16);
            errorView.setPadding(32, 40, 32, 40);
            fixturesContainer.addView(errorView);
        }

        private void createFixtureCard(String homeTeam, String awayTeam, String timeOrScore, int eventKey, String eventDate, int homeTeamKey, int awayTeamKey) {
            MaterialCardView cardView = new MaterialCardView(MainActivity.this);
            cardView.setCardElevation(8);
            cardView.setRadius(16);
            cardView.setCardBackgroundColor(Color.parseColor("#1E1E1E"));
            cardView.setStrokeColor(Color.parseColor("#FF9800"));
            cardView.setStrokeWidth(2);
            cardView.setUseCompatPadding(true);

            LinearLayout cardLayout = new LinearLayout(MainActivity.this);
            cardLayout.setOrientation(LinearLayout.HORIZONTAL);
            cardLayout.setGravity(Gravity.CENTER_VERTICAL);
            cardLayout.setPadding(24, 28, 24, 28);
            cardLayout.setWeightSum(4);

            // Home Team
            TextView tvHome = new TextView(MainActivity.this);
            tvHome.setText(homeTeam);
            tvHome.setTextColor(Color.WHITE);
            tvHome.setTextSize(18);
            tvHome.setGravity(Gravity.START);
            tvHome.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

            // Score / Time
            TextView tvScore = new TextView(MainActivity.this);
            tvScore.setText(timeOrScore);
            tvScore.setTextColor(Color.parseColor("#FF9800"));
            tvScore.setTextSize(18);
            tvScore.setGravity(Gravity.CENTER);
            tvScore.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

            // Away Team
            TextView tvAway = new TextView(MainActivity.this);
            tvAway.setText(awayTeam);
            tvAway.setTextColor(Color.WHITE);
            tvAway.setTextSize(18);
            tvAway.setGravity(Gravity.END);
            tvAway.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

            // Favorite Icon
            ImageView favIcon = new ImageView(MainActivity.this);
            favIcon.setImageResource(R.drawable.ic_launcher_foreground);
            favIcon.setColorFilter(Color.WHITE);
            favIcon.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
            favIcon.setOnClickListener(view -> {
                Toast.makeText(MainActivity.this, "Favorite clicked", Toast.LENGTH_SHORT).show();
            });

            cardLayout.addView(tvHome);
            cardLayout.addView(tvScore);
            cardLayout.addView(tvAway);
            cardLayout.addView(favIcon);

            cardView.addView(cardLayout);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT);
            lp.setMargins(0, 16, 0, 0);
            fixturesContainer.addView(cardView, lp);

            cardView.setOnClickListener(v -> {
                Log.d("MainActivity", "Clicked on: " + homeTeam + " vs " + awayTeam + " | Key: " + eventKey);

                if (eventKey <= 0) {
                    Toast.makeText(MainActivity.this, "⚠️ Invalid match data", Toast.LENGTH_SHORT).show();
                    return;
                }

                Intent intent = new Intent(MainActivity.this, FixtureDetailsActivity.class);
                intent.putExtra("event_key", eventKey);
                intent.putExtra("event_date", eventDate);
                intent.putExtra("home_team_key", homeTeamKey);  // Correct key name
                intent.putExtra("away_team_key", awayTeamKey);
                Log.d("khara", " heyyy " + homeTeamKey + "man " + awayTeamKey);

                startActivity(intent);
            });
        }
    }



}