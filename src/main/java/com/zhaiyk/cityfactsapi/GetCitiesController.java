package com.zhaiyk.cityfactsapi;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class GetCitiesController {

    private final List<City> cities = List.of(
            new City("Almaty", "Kazakhstan", "Biggest city in Kazakhstan"),
            new City("Shymkent","Kazakhstan", "Eldos lives here"),
            new City("London", "UK", "Cool")
    );

    @GetMapping("/")
    public ResponseEntity<List<City>> getCities() {
        return ResponseEntity.ok(cities);
    }

    @GetMapping("/healthz")
    public ResponseEntity<String> healthz() {
        return ResponseEntity.ok("OK");
    }

    @GetMapping("/cities/{name}")
    public ResponseEntity<City> getCity(@PathVariable String name) {
        return cities.stream()
                .filter(city -> city.getName().equalsIgnoreCase(name))
                .findFirst()
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}
