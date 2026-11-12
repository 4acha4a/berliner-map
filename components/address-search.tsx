"use client";
import { useEffect, useRef } from "react";
import { importLibrary } from "@googlemaps/js-api-loader";
import { BERLIN_BOUNDS } from "@/lib/berlin";
import type { LocationController } from "@/lib/location";

export function AddressSearch({ controller }: { controller: LocationController }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    let widget: google.maps.places.PlaceAutocompleteElement | undefined;
    const select = (event: Event) => {
      const { placePrediction } = event as google.maps.places.PlacePredictionSelectEvent;
      if (placePrediction) void controller.address(placePrediction);
    };
    const error = () => {
      controller.fail(controller.begin("address"), "Address search is unavailable. Check your connection and Places API configuration, or select a location on the map.");
    };
    importLibrary("places").then((library) => {
      if (!active || !host.current) return;
      const { PlaceAutocompleteElement } = library as google.maps.PlacesLibrary;
      widget = new PlaceAutocompleteElement({
        includedRegionCodes: ["de"],
        locationRestriction: BERLIN_BOUNDS,
      });
      widget.id = "berlin-address";
      widget.setAttribute("aria-label", "Search Berlin addresses");
      widget.setAttribute("placeholder", "Search Berlin addresses");
      widget.addEventListener("gmp-select", select);
      widget.addEventListener("gmp-error", error);
      host.current.replaceChildren(widget);
    }).catch(() => { if (active) error(); });
    return () => {
      active = false;
      widget?.removeEventListener("gmp-select", select);
      widget?.removeEventListener("gmp-error", error);
      widget?.remove();
    };
  }, [controller]);
  return <div className="address-search" ref={host}><span>Loading address search…</span></div>;
}
