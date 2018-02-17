import React from 'react';
import MapComponent from '../Common/maps-google';
import ContentWrapper from '../Layout/ContentWrapper';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { Grid, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem, Tab, Tabs } from 'react-bootstrap';
import { withGoogleMap, GoogleMap, Marker } from "react-google-maps"
import axios from 'axios';
import {withRouter} from "react-router-dom";


class ViewStore extends React.Component {
    constructor(props) {
        super(props);

        this.state = {store: {}};
    }

    componentDidMount() {
        axios({
            method: 'get',
            url: '/store/' + this.props.match.params.id,
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

    render() {
        return (
            <ContentWrapper class="ViewStore">
                <div className="content-heading">
                    Store
                    <small>Please enter the details</small>
                </div>
                <Row>
                    <Col sm={ 12 }>
                        { /* START panel */ }
                        <Panel header="Store Details">
                            <Tabs defaultActiveKey={2} id="uncontrolled-tab-example">
                                <Tab eventKey={1} title="Dashboard">
                                    Tab 1 content
                                </Tab>
                                <Tab eventKey={2} title="Image Processors">
                                    Tab 2 content
                                </Tab>
                                <Tab eventKey={3} title="Cameras">
                                    Tab 3 content
                                </Tab>
                            </Tabs>
                        </Panel>
                        { /* END panel */ }
                    </Col>
                </Row>
            </ContentWrapper>
        );
    }
}

export default ViewStore;


