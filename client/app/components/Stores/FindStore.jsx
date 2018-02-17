import React from 'react';
import MapComponent from '../Common/maps-google';
import ContentWrapper from '../Layout/ContentWrapper';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { Grid, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem } from 'react-bootstrap';
import { withGoogleMap, GoogleMap, Marker } from "react-google-maps"
import { withRouter} from 'react-router-dom';
import axios from 'axios';
import ReactTable from 'react-table'

const FindStore = withRouter(React.createClass({
    getInitialState() {
        return {stores: [], markers: []};
    },

    componentDidMount() {
        this.geolocate();

        this.refresh();
    },

    refresh() {
        axios({
            method: 'get',
            url: '/store'
        }).then((response) =>
        {
            this.setState({stores: response.data.stores, markers: response.data.stores.map((store) =>
            {
                return {address: store.address, id: store._id, lng: store.coords.lng, lat: store.coords.lat}
            })});
        });
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
                this.setState({mapCenter: geolocation});
            });
        }
    },

    handleChange(key, event) {
        this.setState({[key]: event.target.value});
    },

    render() {
        const storeColumns = [{
            Header: 'Name',
            accessor: 'name' // String-based value accessors!
        }, {
            Header: 'Address',
            accessor: 'address'
        }];

        return (
            <ContentWrapper class="FindStore">
                <div className="content-heading">
                    Find Store
                </div>
                <Row>
                    <Col sm={ 12 }>
                        { /* START panel */ }
                        <Panel header="Store Map">
                            <Row>
                                <Col lg={ 12 }>
                                    <MapComponent center={this.state.mapCenter} markers={this.state.markers} zoom={16}></MapComponent>
                                </Col>
                            </Row>
                            <br/>
                            <Row>
                                <Col lg={ 12 }>
                                    <ReactTable
                                        getTdProps={(state, rowInfo, column, instance) => {
                                            if (rowInfo)
                                            {
                                                return {
                                                    className: 'storeRow',
                                                    onClick: (e, handleOriginal) => {
                                                        this.props.history.push("/store/" + rowInfo.original._id);

                                                        if (handleOriginal) {
                                                            handleOriginal()
                                                        }
                                                    }
                                                }
                                            }
                                            else
                                            {
                                                return {};
                                            }
                                        }}
                                        minRows={5}
                                        data={this.state.stores}
                                        columns={storeColumns}
                                    />
                                </Col>
                            </Row>
                        </Panel>
                        { /* END panel */ }
                    </Col>
                </Row>
            </ContentWrapper>
        );
    }
}));

export default FindStore;


