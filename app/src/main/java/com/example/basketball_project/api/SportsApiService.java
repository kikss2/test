package com.example.basketball_project.api;

import com.example.basketball_project.model.SportsApiResponse;

import retrofit2.Call;
import retrofit2.http.GET;
import retrofit2.http.Query;

public interface SportsApiService {
    @GET("basketball/")
    Call<SportsApiResponse> getFixtures(
            @Query("met") String met,
            @Query("leagueId") int leagueId,
            @Query("from") String from,
            @Query("to") String to,
            @Query("APIkey") String apiKey
    );

}
