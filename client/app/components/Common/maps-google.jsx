import React from 'react';
import { compose, withProps, withState } from "recompose"
import { withGoogleMap, GoogleMap, Marker, InfoWindow } from "react-google-maps"
import _ from 'underscore';
import { Router, Route, Link, History, withRouter } from 'react-router-dom';

const MapComponent = compose(
    withState('open', 'setOpen', {}),
    withProps({
        loadingElement: <div style={{ height: `100%` }} />,
        containerElement: <div style={{ height: `400px` }} />,
        mapElement: <div style={{ height: `100%` }} />,
    }),
    withGoogleMap
)((props) =>
{
    const toggleOpen = (marker) =>
    {
        const newOpen = _.extend({}, props.open, {[marker.id] : !props.open[marker.id]});
        props.setOpen(newOpen);
    };

    return <GoogleMap
        defaultZoom={8}
        defaultCenter={{ lat: 43.645449, lng: -79.393342 }}
        center = {props.center}
        zoom = {props.zoom}
    >
        {props.markers && props.markers.map((marker) =>
            <Marker key={marker.id}
                    position={marker}
                    onClick={toggleOpen.bind(this, marker)}>
                {props.open[marker.id] &&
                    <InfoWindow onCloseClick={toggleOpen.bind(this, marker)}>
                        <div>
                            <p>{marker.address}</p>
                            <br/>
                            <Link to='store-details' title="Store Details">
                                <span>Store Details</span>
                            </Link>
                        </div>
                    </InfoWindow>
                }
            </Marker>
        )}
    </GoogleMap>
});

export default MapComponent;
