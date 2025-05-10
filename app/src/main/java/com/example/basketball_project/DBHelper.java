package com.example.basketball_project;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.HashMap;
import java.util.Map;

public class DBHelper extends SQLiteOpenHelper {
    private static final String DATABASE_NAME = "predictions.db";
    private static final int DATABASE_VERSION = 1;

    public DBHelper(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL(
                "CREATE TABLE predictions (" +
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                        "match_id TEXT, " +
                        "predicted_winner TEXT)"
        );
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        db.execSQL("DROP TABLE IF EXISTS predictions");
        onCreate(db);
    }

    public void insertPrediction(String matchId, String winner) {
        SQLiteDatabase db = this.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("match_id", matchId);
        values.put("predicted_winner", winner);
        db.insert("predictions", null, values);
        db.close();
    }

    public Map<String, Integer> getPredictionPercentage(String matchId) {
        SQLiteDatabase db = this.getReadableDatabase();
        Map<String, Integer> percentageMap = new HashMap<>();

        Cursor totalCursor = db.rawQuery("SELECT COUNT(*) FROM predictions WHERE match_id = ?", new String[]{matchId});
        totalCursor.moveToFirst();
        int total = totalCursor.getInt(0);
        totalCursor.close();

        if (total == 0) return percentageMap;

        Cursor teamCursor = db.rawQuery(
                "SELECT predicted_winner, COUNT(*) as count FROM predictions WHERE match_id = ? GROUP BY predicted_winner",
                new String[]{matchId}
        );

        while (teamCursor.moveToNext()) {
            String team = teamCursor.getString(0);
            int count = teamCursor.getInt(1);
            int percentage = (int) ((count * 100.0f) / total);
            percentageMap.put(team, percentage);
        }

        teamCursor.close();
        db.close();
        return percentageMap;
    }
}
