import React from 'react';
import MapComponent from '../Common/maps-google';
import ContentWrapper from '../Layout/ContentWrapper';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { Grid, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem, Tab, Tabs, Nav, NavItem } from 'react-bootstrap';
import { withGoogleMap, GoogleMap, Marker } from "react-google-maps"
import axios from 'axios';
import {withRouter} from "react-router-dom";
import ReactTable from 'react-table'


class StoreDetails extends React.Component {
    constructor(props) {
        super(props);

        this.state = {isUploading: false, storeLayoutCacheBreaker: ""};
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
                                <img className='store-image' src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout?" + this.state.storeLayoutCacheBreaker} />

                                {this.state.frame &&
                                    this.state.frame.people.map((person) =>
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

                                {this.state.showProgress && <div data-label={this.state.progress} className="radial-bar radial-bar-1 radial-bar-lg"></div>}
                            </div>
                        </Col>
                    </Row>
                </Panel>
            </div>
        );
    }
}

export default withRouter(StoreDetails);


