package com.zhaiyk.cityfactsapi;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class City {

    private String name;
    private String country;
    private String fact;

    public City(String name, String country, String fact) {
        this.name = name;
        this.country = country;
        this.fact = fact;
    }

}