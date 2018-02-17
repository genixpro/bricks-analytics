import React from 'react';
import MapComponent from '../Common/maps-google';
import ContentWrapper from '../Layout/ContentWrapper';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { Grid, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem } from 'react-bootstrap';
import { withGoogleMap, GoogleMap, Marker } from "react-google-maps"
import axios from 'axios';


const NewStore = React.createClass({
    getInitialState() {
        return {name: '', address: ''};
    },

    componentDidMount() {
        this.addressAutocomplete = new google.maps.places.Autocomplete(
            /** @type {!HTMLInputElement} */(document.getElementById('addressAutocomplete')),
            {types: ['geocode']});

        this.addressAutocomplete.addListener('place_changed', () =>
        {
            var place = this.addressAutocomplete.getPlace();

            const lng = place.geometry.location.lng();
            const lat = place.geometry.location.lat();

            this.setState({address: place.formatted_address, lat, lng, mapCenter: {lat, lng}});
        });

        this.geolocate()
    },

    // Bias the autocomplete object to the user's geographical location,
    // as supplied by the browser's 'navigator.geolocation' object.
    geolocate() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition((position) => {
                var geolocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                var circle = new google.maps.Circle({
                    center: geolocation,
                    radius: position.coords.accuracy
                });
                this.addressAutocomplete.setBounds(circle.getBounds());
                this.setState({mapCenter: geolocation});
            });
        }
    },

    handleSubmit(event) {
        event.preventDefault();
        axios({
            method: 'post',
            url: '/store',
            data: {
                name: this.state.name,
                address: this.state.address,
                coords: {
                    lat: this.state.lat,
                    lng: this.state.lng
                },
                more: "fixed"
            }
        })
    },

    handleChange(key, event) {
        this.setState({[key]: event.target.value});
    },

    render() {
        return (
            <ContentWrapper class="NewStore">
                <div className="content-heading">
                    New Store
                    <small>Please enter the details</small>
                </div>
                <Row>
                    <Col sm={ 6 }>
                        { /* START panel */ }
                        <Panel header="Store Details">
                            <form className="form-horizontal" onSubmit={this.handleSubmit}>
                                <FormGroup>
                                    <label className="col-lg-2 control-label">Name</label>
                                    <Col lg={ 10 }>
                                        <FormControl type="text" placeholder="Name" className="form-control" value={this.state.name} onChange={this.handleChange.bind(this, "name")}/>
                                    </Col>
                                </FormGroup>
                                <FormGroup>
                                    <label className="col-lg-2 control-label">Address</label>
                                    <Col lg={ 10 }>
                                        <FormControl type="text" id="addressAutocomplete" placeholder="Address" className="form-control" value={this.state.address} onChange={this.handleChange.bind(this, "address")}/>
                                    </Col>
                                </FormGroup>
                                <Row>
                                    <Col lgOffset={2} lg={ 10 }>
                                        <MapComponent center={this.state.mapCenter} markers={[this.state.mapCenter]} zoom={16}></MapComponent>
                                    </Col>
                                </Row>
                                <FormGroup>
                                    <Col lgOffset={ 2 } lg={ 10 }>
                                        <Button type="submit" bsStyle="primary" bsSize="small">Create</Button>
                                    </Col>
                                </FormGroup>
                            </form>
                        </Panel>
                        { /* END panel */ }
                    </Col>
                </Row>
            </ContentWrapper>
        );
    }
});

export default NewStore;


