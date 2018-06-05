import React from 'react';
import MapComponent from '../Common/maps-google';
import ContentWrapper from '../Layout/ContentWrapper';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { Grid, Popover, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem, Tab, Tabs, Nav, NavItem } from 'react-bootstrap';
import { withGoogleMap, GoogleMap, Marker } from "react-google-maps"
import axios from 'axios';
import {withRouter} from "react-router-dom";
import ReactTable from 'react-table'
import ZoneEditor from './ZoneEditor';
import _ from 'underscore';


class StoreDetails extends React.Component {
    constructor(props) {
        super(props);
    }

    componentDidMount()
    {
        var headers = {durable: false, "auto-delete": false, exclusive: false};
        this.storeSubscription = this.props.messagingClient.subscribe("/exchange/store-frames-" + this.props.store._id, (message) =>
        {
            const body = JSON.parse(message.body);
            this.setState({frame: body});
        }, headers);
    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {
        if (this.storeSubscription)
        {
            this.storeSubscription.unsubscribe();
        }
    }

    shouldComponentUpdate(nextProps, nextState)
    {
        if (nextProps.store._id !== this.props.store._id)
        {
            return true;
        }
        else
        {
            return false;
        }
    }


    uploadNewStoreMap()
    {
        const upload = document.createElement('input');
        upload.setAttribute('type', 'file');
        const self = this;
        function handleFiles() {
            var fileList = this.files;

            axios({
                method: 'put',
                url: '/store/' + self.props.match.params.storeId + "/store_layout",
                data: fileList[0],
                onUploadProgress: function (progressEvent) {
                    // Do whatever you want with the native progress event
                    if (progressEvent.loaded < progressEvent.total)
                    {
                        self.setState({showProgress: true, progress: (progressEvent.loaded * 100 / progressEvent.total)});
                    }
                },
            }).then((response) =>
            {
                self.setState({showProgress: false, storeLayoutCacheBreaker: Date.now().toString()});
            });
        }

        upload.addEventListener("change", handleFiles, false);
        upload.click();
    }

    updateZones(zones)
    {
        const store = this.props.store;
        store.zones = zones;
        this.props.updateStore(store);
    }

    updateZoneEditorState(zoneEditorState, callback)
    {
        const newEditorState = _.clone(this.props.editorState);
        newEditorState.zoneEditor = zoneEditorState;
        this.setState(newEditorState, callback);
    }


    // Override setState
    setState(newState, callback)
    {
        this.props.updateEditorState(_.extend({}, this.props.editorState, newState), callback);
    }


    render() {

        const personImageOffsetX = 32;
        const personImageOffsetY = 32;

        return (
            <div>
                <br/>
                <Panel header="Store Details">
                    <Row>
                        <Col lg={6}>
                            <h2>Store Map</h2>
                            <div className="storeMap" onClick={this.uploadNewStoreMap.bind(this)}>
                                <i className="fa fa-upload" />
                                <img className='store-image' src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout?" + this.props.editorState.storeLayoutCacheBreaker} />

                                {this.props.frame &&
                                this.props.frame.people.map((person) =>
                                    <img className="person-location"
                                         src='/img/person.png'
                                         style={{
                                             "left": person[1][0] - personImageOffsetX + 300,
                                             "top": person[1][1] - personImageOffsetY + 300
                                         }}
                                    />
                                )
                                }

                                <div className="overlay"></div>

                                {this.props.editorState.showProgress && <div data-label={this.props.editorState.progress} className="radial-bar radial-bar-1 radial-bar-lg"></div>}
                            </div>
                        </Col>
                    </Row>
                    {
                        this.props.store ?
                            <Row>
                                <Col xs={12}>
                                    <h2>Zones</h2>

                                    <ZoneEditor
                                        src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout?" + this.props.editorState.storeLayoutCacheBreaker}
                                        zones={this.props.store.zones ? this.props.store.zones : []}
                                        editorState={this.props.editorState ? this.props.editorState.zoneEditor : {}}
                                        updateZones={this.updateZones.bind(this)}
                                        updateEditorState={this.updateZoneEditorState.bind(this)}
                                    />
                                </Col>
                            </Row>
                            : null

                    }
                </Panel>
            </div>
        );
    }
}

export default withRouter(StoreDetails);


