import React from 'react';
import MapComponent from '../Common/maps-google';
import ContentWrapper from '../Layout/ContentWrapper';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { Grid, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem, Tab, Tabs, Nav, NavItem } from 'react-bootstrap';
import { withGoogleMap, GoogleMap, Marker } from "react-google-maps"
import axios from 'axios';
import {withRouter,Route} from "react-router-dom";
import ReactTable from 'react-table'
import { withProps, branch } from 'recompose';
import StoreDetails from "./StoreDetails";
import StoreCameras from "./StoreCameras";
import StoreImageProcessors from "./StoreImageProcessors";
import _ from 'underscore';


class ViewStore extends React.Component {
    constructor(props) {
        super(props);

        this.state = {store: {}, isUploading: false, storeLayoutCacheBreaker: ""};
    }

    componentDidMount() {
        axios({
            method: 'get',
            url: '/store/' + this.props.match.params.storeId,
        }).then((response) =>
        {
            this.setState({store: response.data})
        });
    }

    toggle(tab) {
        if (this.state.activeTab !== tab) {
            this.setState({
                activeTab: tab
            });
        }
    }

    handleSelect(tab)
    {
        if (tab === "1")
        {
            this.props.history.push("/store/" + this.props.match.params.storeId + "/details");
        }
        else if (tab === "2")
        {
            this.props.history.push("/store/" + this.props.match.params.storeId + "/image_processors");
        }
        else if (tab === "3")
        {
            this.props.history.push("/store/" + this.props.match.params.storeId + "/cameras");
        }
    }


    render() {
        const cameraColumns = [{
            Header: 'ID',
            accessor: 'id' // String-based value accessors!
        }];

        return (
            <ContentWrapper class="ViewStore">
                <div className="content-heading">
                    Store
                    <small>Please enter the details</small>
                </div>
                <Row>
                    <Col sm={ 12 }>
                        { /* START panel */ }
                        <Nav bsStyle="tabs"  activeHref={this.props.location.pathname} onSelect={k => this.handleSelect(k)}>
                            <NavItem eventKey="1" href={"/store/" + this.props.match.params.storeId + "/details"}>
                                Details
                            </NavItem>
                            <NavItem eventKey="2" href={"/store/" + this.props.match.params.storeId + "/image_processors"}>
                                Image Processors
                            </NavItem>
                            <NavItem eventKey="3" href={"/store/" + this.props.match.params.storeId + "/cameras"}>
                                Cameras
                            </NavItem>
                        </Nav>

                        {
                            this.state.store._id &&
                             <div>
                                 <Route path="/store/:storeId/details" component={withProps(_.extend({}, this.props, {store: this.state.store}))(StoreDetails)} />
                                 <Route path="/store/:storeId/image_processors" component={withProps(_.extend({}, this.props, {store: this.state.store}))(StoreImageProcessors)} />
                                 <Route path="/store/:storeId/cameras" component={withProps(_.extend({}, this.props, {store: this.state.store}))(StoreCameras)} />
                                 <Route path="/store/:storeId/camera/:cameraId" component={withProps(_.extend({}, this.props, {store: this.state.store}))(StoreCameras)} />
                             </div>
                        }
                        { /* END panel */ }
                    </Col>
                </Row>
            </ContentWrapper>
        );
    }
}

export default withRouter(ViewStore);


